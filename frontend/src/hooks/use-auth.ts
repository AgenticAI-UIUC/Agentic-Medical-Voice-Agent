'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { loginAccessToken } from '@/lib/api/login';
import {
  changeMyPassword,
  getCurrentUser,
  updateMe,
  type ChangeMyPasswordInput,
  type UpdateMeInput,
} from '@/lib/api/users';

import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from '@/lib/api/auth';

export function useLoginMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: loginAccessToken,
    onSuccess: async (data) => {
      setAccessToken(data.access_token);
      try {
        const user = await getCurrentUser(data.access_token);
        queryClient.setQueryData(['auth', 'me'], user);
      } catch {
        await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
      }
    },
  });
}

export function useCurrentUserQuery(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const token = getAccessToken();
      if (!token) throw new Error('Not authenticated');
      return getCurrentUser(token);
    },
    enabled: options?.enabled ?? true,
    retry: false,
  });
}

export function logout() {
  clearAccessToken();
}

export function useUpdateMeMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: UpdateMeInput) => {
      const token = getAccessToken();
      if (!token) throw new Error('Not authenticated');
      return updateMe(token, input);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
    },
  });
}

export function useChangeMyPasswordMutation() {
  return useMutation({
    mutationFn: async (input: ChangeMyPasswordInput) => {
      const token = getAccessToken();
      if (!token) throw new Error('Not authenticated');
      return changeMyPassword(token, input);
    },
  });
}
