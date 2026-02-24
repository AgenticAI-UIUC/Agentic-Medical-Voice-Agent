import { apiFetch } from './client';

export type DoctorCard = {
  id: string;
  full_name: string;
  image_url: string | null;
  specialties: string[];
};

export type DoctorSlot = {
  id: string;
  start_at: string;
  end_at: string;
  status: 'AVAILABLE' | 'BOOKED' | 'BLOCKED';
  appointment_id: string | null;
};

export type DaySchedule = {
  date: string;
  slots: DoctorSlot[];
};

export type DoctorSchedule = {
  doctor_id: string;
  doctor_name: string;
  start_date: string;
  days: number;
  schedule: DaySchedule[];
};

export function getDoctors(token: string) {
  return apiFetch<DoctorCard[]>('/api/v1/doctors?active_only=true', {
    method: 'GET',
    token,
  });
}

export function getDoctorSchedule(
  token: string,
  doctorId: string,
  params: { startDate: string; days?: number },
) {
  const search = new URLSearchParams();
  search.set('start_date', params.startDate);
  search.set('days', String(params.days ?? 7));

  return apiFetch<DoctorSchedule>(`/api/v1/doctors/${doctorId}/schedule?${search.toString()}`, {
    method: 'GET',
    token,
  });
}
