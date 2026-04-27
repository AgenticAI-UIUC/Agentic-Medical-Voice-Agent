'use client';

import { useQuery } from '@tanstack/react-query';

import { getAccessToken } from '@/lib/api/auth';
import { getStaffCalls } from '@/lib/api/calls';

export const callsQueryKey = (params: { status?: string; limit?: number }) =>
  ['calls', params.status ?? 'all', params.limit ?? 50] as const;

function requireToken() {
  const token = getAccessToken();
  if (!token) throw new Error('Not authenticated');
  return token;
}

export function useStaffCallsQuery(params: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: callsQueryKey(params),
    queryFn: async () => {
      const token = requireToken();
      return getStaffCalls(token, params);
    },
    refetchInterval: 4_000,
    retry: false,
    staleTime: 0,
  });
}
