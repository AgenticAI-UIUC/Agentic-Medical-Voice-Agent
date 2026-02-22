import { createClient, type SupabaseClient } from '@supabase/supabase-js';

export type ArtifactKind =
  | 'raw_turn'
  | 'recording_reference'
  | 'redacted_transcript'
  | 'structured_summary';

const DEFAULT_RETENTION_DAYS: Record<ArtifactKind, number> = {
  raw_turn: 7,
  recording_reference: 30,
  redacted_transcript: 90,
  structured_summary: 365,
};

const REQUIRED_BAA_VENDORS = ['supabase', 'vapi'];

let supabaseAdminClient: SupabaseClient | null = null;

function parseVendorList(value?: string): string[] {
  if (!value) {
    return [];
  }

  return value
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function assertRetentionOrdering(days: Record<ArtifactKind, number>) {
  const orderingIsStrict =
    days.raw_turn < days.recording_reference &&
    days.recording_reference <= days.redacted_transcript &&
    days.redacted_transcript < days.structured_summary;

  if (!orderingIsStrict) {
    throw new Error(
      'Invalid retention ordering. Requirement: raw shortest, summary longest.'
    );
  }
}

export function getArtifactRetentionDays(kind: ArtifactKind): number {
  const byEnv: Record<ArtifactKind, number> = {
    raw_turn: Number(process.env.RETENTION_RAW_TURN_DAYS ?? DEFAULT_RETENTION_DAYS.raw_turn),
    recording_reference: Number(
      process.env.RETENTION_RECORDING_DAYS ?? DEFAULT_RETENTION_DAYS.recording_reference
    ),
    redacted_transcript: Number(
      process.env.RETENTION_REDACTED_TRANSCRIPT_DAYS ?? DEFAULT_RETENTION_DAYS.redacted_transcript
    ),
    structured_summary: Number(
      process.env.RETENTION_STRUCTURED_SUMMARY_DAYS ??
        DEFAULT_RETENTION_DAYS.structured_summary
    ),
  };

  assertRetentionOrdering(byEnv);

  return byEnv[kind];
}

export function getArtifactExpiry(kind: ArtifactKind): string {
  const expiresAt = new Date();
  expiresAt.setUTCDate(expiresAt.getUTCDate() + getArtifactRetentionDays(kind));
  return expiresAt.toISOString();
}

export function assertHipaaReadyConfiguration() {
  if (process.env.HIPAA_READY_MODE !== 'true') {
    throw new Error('HIPAA_READY_MODE must be true before persisting PHI to Supabase.');
  }

  const requiredVendors = parseVendorList(process.env.HIPAA_REQUIRED_BAA_VENDORS).length
    ? parseVendorList(process.env.HIPAA_REQUIRED_BAA_VENDORS)
    : REQUIRED_BAA_VENDORS;

  const signedVendors = new Set(parseVendorList(process.env.SIGNED_BAA_VENDORS));
  const missingVendors = requiredVendors.filter((vendor) => !signedVendors.has(vendor));

  if (missingVendors.length > 0) {
    throw new Error(
      `Missing signed BAAs for vendors in data path: ${missingVendors.join(', ')}.`
    );
  }
}

export function getSupabaseAdminClient(): SupabaseClient {
  assertHipaaReadyConfiguration();

  if (supabaseAdminClient) {
    return supabaseAdminClient;
  }

  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.');
  }

  supabaseAdminClient = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  return supabaseAdminClient;
}

export function getRecordingBucketName(): string {
  return process.env.SUPABASE_CALL_AUDIO_BUCKET ?? 'call-audio';
}
