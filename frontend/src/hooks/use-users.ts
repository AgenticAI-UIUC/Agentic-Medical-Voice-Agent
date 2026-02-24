'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getAccessToken } from '@/lib/api/auth';
import {
  createUser,
  deleteUser,
  getUsers,
  updateUser,
  type UserCreateInput,
  type UserUpdateInput,
} from '@/lib/api/users';

export const usersQueryKey = (params: { skip: number; limit: number }) =>
  ['users', params.skip, params.limit] as const;

function requireToken() {
  const token = getAccessToken();
  if (!token) throw new Error('Not authenticated');
  return token;
}

export function useUsersQuery(params: { skip: number; limit: number }) {
  return useQuery({
    queryKey: usersQueryKey(params),
    queryFn: async () => {
      const token = requireToken();
      return getUsers(token, params);
    },
    retry: false,
  });
}

export function useCreateUserMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: UserCreateInput) => {
      const token = requireToken();
      return createUser(token, input);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useUpdateUserMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: { userId: string; input: UserUpdateInput }) => {
      const token = requireToken();
      return updateUser(token, params.userId, params.input);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useDeleteUserMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: string) => {
      const token = requireToken();
      return deleteUser(token, userId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
