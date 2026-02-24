import { apiFetch } from './client';

export type UserPublic = {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
};

export type UsersPublic = {
  data: UserPublic[];
  count: number;
};

export type UserCreateInput = {
  email: string;
  full_name?: string | null;
  is_active?: boolean;
  is_superuser?: boolean;
  password: string;
};

export type UserUpdateInput = {
  email?: string;
  full_name?: string | null;
  is_active?: boolean;
  is_superuser?: boolean;
  password?: string;
};

export type UpdateMeInput = {
  email?: string | null;
  full_name?: string | null;
};

export type ChangeMyPasswordInput = {
  current_password: string;
  new_password: string;
};

export function getCurrentUser(token: string) {
  return apiFetch<UserPublic>('/api/v1/users/me', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function getUsers(
  token: string,
  params?: { skip?: number; limit?: number },
) {
  const search = new URLSearchParams();
  if (params?.skip !== undefined) search.set('skip', String(params.skip));
  if (params?.limit !== undefined) search.set('limit', String(params.limit));

  const qs = search.toString();
  const path = `/api/v1/users/${qs ? `?${qs}` : ''}`;

  return apiFetch<UsersPublic>(path, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function createUser(token: string, input: UserCreateInput) {
  return apiFetch<UserPublic>('/api/v1/users/', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      email: input.email,
      full_name: input.full_name ?? null,
      is_active: input.is_active ?? true,
      is_superuser: input.is_superuser ?? false,
      password: input.password,
    }),
  });
}

export function updateUser(
  token: string,
  userId: string,
  input: UserUpdateInput,
) {
  return apiFetch<UserPublic>(`/api/v1/users/${userId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}

export function deleteUser(token: string, userId: string) {
  return apiFetch<{ message: string }>(`/api/v1/users/${userId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function updateMe(token: string, input: UpdateMeInput) {
  return apiFetch('/api/v1/users/me', {
    method: 'PATCH',
    token,
    body: JSON.stringify(input),
  });
}

export async function changeMyPassword(
  token: string,
  input: ChangeMyPasswordInput,
) {
  return apiFetch('/api/v1/users/me/password', {
    method: 'PATCH',
    token,
    body: JSON.stringify(input),
  });
}
