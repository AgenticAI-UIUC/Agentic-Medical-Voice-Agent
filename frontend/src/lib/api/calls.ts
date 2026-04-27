import { apiFetch } from './client';

export type PatientSummary = {
  id?: string | null;
  uin?: string | null;
  full_name?: string | null;
  phone?: string | null;
};

export type CallAppointment = {
  id: string;
  status?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  urgency?: string | null;
  reason?: string | null;
  symptoms?: string | null;
  doctors?: {
    full_name?: string | null;
  } | null;
};

export type StaffCall = {
  id: string;
  call_id: string;
  call_status: string;
  outcome?: string | null;
  ended_reason?: string | null;
  summary?: string | null;
  transcript: unknown;
  created_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  last_event_at?: string | null;
  patient?: PatientSummary | null;
  appointments: CallAppointment[];
};

export function getStaffCalls(
  token: string,
  params?: { status?: string; limit?: number },
) {
  const search = new URLSearchParams();
  if (params?.status) search.set('status', params.status);
  if (params?.limit !== undefined) search.set('limit', String(params.limit));

  const qs = search.toString();
  const path = `/api/v1/admin/calls${qs ? `?${qs}` : ''}`;

  return apiFetch<StaffCall[]>(path, {
    method: 'GET',
    token,
  });
}
