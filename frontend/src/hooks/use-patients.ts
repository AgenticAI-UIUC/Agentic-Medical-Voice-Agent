'use client';

import { useQuery } from '@tanstack/react-query';

import { getAccessToken } from '@/lib/api/auth';
import { getAppointments, getPatients } from '@/lib/api/patients';

export const patientsQueryKey = (params: { limit?: number }) =>
  ['patients', params.limit ?? 200] as const;

export const appointmentsQueryKey = (params: {
  status?: string;
  limit?: number;
}) => ['appointments', params.status ?? 'all', params.limit ?? 200] as const;

function requireToken() {
  const token = getAccessToken();
  if (!token) throw new Error('Not authenticated');
  return token;
}

export function usePatientsQuery(params: { limit?: number } = {}) {
  return useQuery({
    queryKey: patientsQueryKey(params),
    queryFn: async () => {
      const token = requireToken();
      return getPatients(token, params);
    },
    retry: false,
  });
}

export function useAppointmentsQuery(
  params: { status?: string; limit?: number } = {},
) {
  return useQuery({
    queryKey: appointmentsQueryKey(params),
    queryFn: async () => {
      const token = requireToken();
      return getAppointments(token, params);
    },
    retry: false,
  });
}
