begin;

create extension if not exists pgcrypto;

create or replace function app_current_role()
returns text
language sql
stable
as $$
  select coalesce(auth.jwt() ->> 'app_role', '');
$$;

create or replace function app_has_role(required_role text)
returns boolean
language sql
stable
as $$
  select app_current_role() = required_role;
$$;

create or replace function app_has_any_role(required_roles text[])
returns boolean
language sql
stable
as $$
  select app_current_role() = any(required_roles);
$$;

create table if not exists call_sessions (
  id uuid primary key default gen_random_uuid(),
  call_id text not null unique,
  call_type text,
  status text,
  assistant_id text,
  patient_identifier text,
  started_at timestamptz,
  ended_at timestamptz,
  duration_seconds integer,
  ended_reason text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists call_turns_raw (
  id bigserial primary key,
  call_id text not null references call_sessions(call_id) on delete cascade,
  speaker text not null check (speaker in ('user', 'assistant', 'system', 'function')),
  uttered_at timestamptz not null,
  utterance_text text not null,
  confidence_score numeric(5,4),
  tool_call_context jsonb not null default '{}'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_call_turns_raw_call_id on call_turns_raw(call_id);
create index if not exists idx_call_turns_raw_expires_at on call_turns_raw(expires_at);

create table if not exists call_recordings (
  id uuid primary key default gen_random_uuid(),
  call_id text not null unique references call_sessions(call_id) on delete cascade,
  provider_recording_url text,
  storage_bucket text,
  storage_object_path text,
  metadata jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_call_recordings_expires_at on call_recordings(expires_at);

create table if not exists call_transcript_artifacts (
  id uuid primary key default gen_random_uuid(),
  call_id text not null references call_sessions(call_id) on delete cascade,
  artifact_type text not null,
  transcript_text text not null,
  redaction_version text,
  metadata jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  check (artifact_type in ('redacted_staff'))
);

create index if not exists idx_call_transcript_artifacts_call_id
  on call_transcript_artifacts(call_id);
create index if not exists idx_call_transcript_artifacts_expires_at
  on call_transcript_artifacts(expires_at);

create table if not exists call_structured_summaries (
  id uuid primary key default gen_random_uuid(),
  call_id text not null unique references call_sessions(call_id) on delete cascade,
  intent text not null,
  outcome text not null,
  reason_codes text[] not null default '{}',
  next_action text not null,
  summary_text text,
  analytics jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_call_structured_summaries_expires_at
  on call_structured_summaries(expires_at);

create table if not exists artifact_retention_policies (
  artifact_type text primary key,
  retention_days integer not null check (retention_days > 0),
  description text,
  updated_at timestamptz not null default now(),
  check (artifact_type in ('raw_turn', 'recording_reference', 'redacted_transcript', 'structured_summary'))
);

insert into artifact_retention_policies (artifact_type, retention_days, description)
values
  ('raw_turn', 7, 'Raw call turns with highest PHI risk and shortest retention.'),
  ('recording_reference', 30, 'Recording metadata and object references.'),
  ('redacted_transcript', 90, 'Redacted transcript for staff review.'),
  ('structured_summary', 365, 'Structured summary retained for analytics and longitudinal reporting.')
on conflict (artifact_type) do nothing;

create table if not exists phi_access_audit_logs (
  id bigserial primary key,
  actor_id text not null,
  actor_role text not null,
  action text not null,
  table_name text not null,
  record_id text,
  call_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_phi_access_audit_logs_call_id
  on phi_access_audit_logs(call_id);
create index if not exists idx_phi_access_audit_logs_created_at
  on phi_access_audit_logs(created_at);

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_call_sessions_updated_at on call_sessions;
create trigger trg_call_sessions_updated_at
before update on call_sessions
for each row
execute function set_updated_at();

drop trigger if exists trg_call_recordings_updated_at on call_recordings;
create trigger trg_call_recordings_updated_at
before update on call_recordings
for each row
execute function set_updated_at();

drop trigger if exists trg_call_structured_summaries_updated_at on call_structured_summaries;
create trigger trg_call_structured_summaries_updated_at
before update on call_structured_summaries
for each row
execute function set_updated_at();

create or replace function enforce_retention_policy_ordering()
returns trigger
language plpgsql
as $$
declare
  raw_days integer;
  recording_days integer;
  redacted_days integer;
  summary_days integer;
begin
  select retention_days into raw_days
  from artifact_retention_policies where artifact_type = 'raw_turn';

  select retention_days into recording_days
  from artifact_retention_policies where artifact_type = 'recording_reference';

  select retention_days into redacted_days
  from artifact_retention_policies where artifact_type = 'redacted_transcript';

  select retention_days into summary_days
  from artifact_retention_policies where artifact_type = 'structured_summary';

  if raw_days is null or recording_days is null or redacted_days is null or summary_days is null then
    return null;
  end if;

  if raw_days >= recording_days or recording_days > redacted_days or redacted_days >= summary_days then
    raise exception 'Invalid retention ordering: raw_turn < recording_reference <= redacted_transcript < structured_summary must hold';
  end if;

  return null;
end;
$$;

drop trigger if exists trg_retention_policy_ordering on artifact_retention_policies;
create constraint trigger trg_retention_policy_ordering
after insert or update or delete on artifact_retention_policies
deferrable initially deferred
for each row
execute function enforce_retention_policy_ordering();

create or replace function log_phi_write()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  payload jsonb;
  row_id text;
  call_key text;
begin
  if tg_op = 'DELETE' then
    payload := to_jsonb(old);
  else
    payload := to_jsonb(new);
  end if;

  row_id := coalesce(payload ->> 'id', payload ->> 'call_id', 'n/a');
  call_key := payload ->> 'call_id';

  insert into phi_access_audit_logs (
    actor_id,
    actor_role,
    action,
    table_name,
    record_id,
    call_id,
    metadata
  )
  values (
    coalesce(auth.uid()::text, 'system-trigger'),
    coalesce(app_current_role(), 'system_service'),
    tg_op,
    tg_table_name,
    row_id,
    call_key,
    jsonb_build_object('source', 'db-trigger')
  );

  if tg_op = 'DELETE' then
    return old;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_audit_call_sessions on call_sessions;
create trigger trg_audit_call_sessions
after insert or update or delete on call_sessions
for each row
execute function log_phi_write();

drop trigger if exists trg_audit_call_turns_raw on call_turns_raw;
create trigger trg_audit_call_turns_raw
after insert or update or delete on call_turns_raw
for each row
execute function log_phi_write();

drop trigger if exists trg_audit_call_recordings on call_recordings;
create trigger trg_audit_call_recordings
after insert or update or delete on call_recordings
for each row
execute function log_phi_write();

drop trigger if exists trg_audit_call_transcript_artifacts on call_transcript_artifacts;
create trigger trg_audit_call_transcript_artifacts
after insert or update or delete on call_transcript_artifacts
for each row
execute function log_phi_write();

drop trigger if exists trg_audit_call_structured_summaries on call_structured_summaries;
create trigger trg_audit_call_structured_summaries
after insert or update or delete on call_structured_summaries
for each row
execute function log_phi_write();

create or replace function purge_expired_call_artifacts()
returns table (artifact_type text, deleted_count bigint)
language plpgsql
security definer
set search_path = public
as $$
declare
  deleted_raw bigint;
  deleted_recordings bigint;
  deleted_redacted bigint;
  deleted_summaries bigint;
begin
  delete from call_turns_raw where expires_at <= now();
  get diagnostics deleted_raw = row_count;

  delete from call_recordings where expires_at <= now();
  get diagnostics deleted_recordings = row_count;

  delete from call_transcript_artifacts where expires_at <= now();
  get diagnostics deleted_redacted = row_count;

  delete from call_structured_summaries where expires_at <= now();
  get diagnostics deleted_summaries = row_count;

  return query
  values
    ('raw_turn', deleted_raw),
    ('recording_reference', deleted_recordings),
    ('redacted_transcript', deleted_redacted),
    ('structured_summary', deleted_summaries);
end;
$$;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('call-audio', 'call-audio', false, 104857600, array['audio/mpeg', 'audio/mp3', 'audio/wav'])
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

alter table call_sessions enable row level security;
alter table call_turns_raw enable row level security;
alter table call_recordings enable row level security;
alter table call_transcript_artifacts enable row level security;
alter table call_structured_summaries enable row level security;
alter table artifact_retention_policies enable row level security;
alter table phi_access_audit_logs enable row level security;

create policy call_sessions_select_policy on call_sessions
for select
using (app_has_any_role(array['clinical_staff', 'compliance_officer']));

create policy call_sessions_write_policy on call_sessions
for all
using (app_has_role('system_service'))
with check (app_has_role('system_service'));

create policy call_turns_raw_select_policy on call_turns_raw
for select
using (app_has_role('compliance_officer'));

create policy call_turns_raw_write_policy on call_turns_raw
for all
using (app_has_role('system_service'))
with check (app_has_role('system_service'));

create policy call_recordings_select_policy on call_recordings
for select
using (app_has_role('compliance_officer'));

create policy call_recordings_write_policy on call_recordings
for all
using (app_has_role('system_service'))
with check (app_has_role('system_service'));

create policy call_transcript_artifacts_select_policy on call_transcript_artifacts
for select
using (app_has_any_role(array['clinical_staff', 'compliance_officer']));

create policy call_transcript_artifacts_write_policy on call_transcript_artifacts
for all
using (app_has_role('system_service'))
with check (app_has_role('system_service'));

create policy call_structured_summaries_select_policy on call_structured_summaries
for select
using (app_has_any_role(array['clinical_staff', 'compliance_officer']));

create policy call_structured_summaries_write_policy on call_structured_summaries
for all
using (app_has_role('system_service'))
with check (app_has_role('system_service'));

create policy artifact_retention_policies_select_policy on artifact_retention_policies
for select
using (app_has_role('compliance_officer'));

create policy artifact_retention_policies_write_policy on artifact_retention_policies
for all
using (app_has_role('system_service'))
with check (app_has_role('system_service'));

create policy phi_access_audit_logs_select_policy on phi_access_audit_logs
for select
using (app_has_role('compliance_officer'));

create policy phi_access_audit_logs_write_policy on phi_access_audit_logs
for all
using (app_has_role('system_service'))
with check (app_has_role('system_service'));

do $$
begin
  begin
    alter table storage.objects enable row level security;

    drop policy if exists call_audio_select_policy on storage.objects;
    create policy call_audio_select_policy on storage.objects
    for select
    using (
      bucket_id = 'call-audio'
      and app_has_role('compliance_officer')
    );

    drop policy if exists call_audio_insert_policy on storage.objects;
    create policy call_audio_insert_policy on storage.objects
    for insert
    with check (
      bucket_id = 'call-audio'
      and app_has_role('system_service')
    );

    drop policy if exists call_audio_update_policy on storage.objects;
    create policy call_audio_update_policy on storage.objects
    for update
    using (
      bucket_id = 'call-audio'
      and app_has_role('system_service')
    )
    with check (
      bucket_id = 'call-audio'
      and app_has_role('system_service')
    );

    drop policy if exists call_audio_delete_policy on storage.objects;
    create policy call_audio_delete_policy on storage.objects
    for delete
    using (
      bucket_id = 'call-audio'
      and app_has_role('system_service')
    );
  exception
    when insufficient_privilege then
      raise notice 'Skipping storage.objects policy setup due to insufficient privileges. Configure Storage RLS in Supabase Dashboard.';
  end;
end;
$$;

commit;
