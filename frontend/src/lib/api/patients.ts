import { apiFetch } from './client';

export type Patient = {
  id: string;
  uin: string;
  full_name: string;
  phone: string;
  email?: string | null;
  allergies?: string | null;
  created_at?: string | null;
};

export type PatientAppointment = {
  id: string;
  patient_id: string;
  doctor_id: string;
  specialty_id?: string | null;
  conversation_id?: string | null;
  follow_up_from_id?: string | null;
  start_at: string;
  end_at: string;
  reason?: string | null;
  symptoms?: string | null;
  urgency: 'ROUTINE' | 'URGENT' | 'ER' | string;
  status: 'CONFIRMED' | 'CANCELLED' | 'COMPLETED' | 'NO_SHOW' | string;
  vapi_call_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  doctors?: {
    full_name?: string | null;
  } | null;
  specialties?: {
    name?: string | null;
  } | null;
  patients?: {
    uin?: string | null;
    full_name?: string | null;
  } | null;
};

export function getPatients(token: string, params?: { limit?: number }) {
  const search = new URLSearchParams();
  if (params?.limit !== undefined) search.set('limit', String(params.limit));

  const qs = search.toString();
  return apiFetch<Patient[]>(`/api/v1/admin/patients${qs ? `?${qs}` : ''}`, {
    method: 'GET',
    token,
  });
}

export function getAppointments(
  token: string,
  params?: { status?: string; limit?: number },
) {
  const search = new URLSearchParams();
  if (params?.status) search.set('status', params.status);
  if (params?.limit !== undefined) search.set('limit', String(params.limit));

  const qs = search.toString();
  return apiFetch<PatientAppointment[]>(
    `/api/v1/admin/appointments${qs ? `?${qs}` : ''}`,
    {
      method: 'GET',
      token,
    },
  );
}
