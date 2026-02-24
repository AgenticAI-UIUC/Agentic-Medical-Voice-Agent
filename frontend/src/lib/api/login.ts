import { apiFetch } from './client';

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export async function loginAccessToken(input: {
  username: string;
  password: string;
}): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.set('username', input.username);
  form.set('password', input.password);

  return apiFetch<TokenResponse>('/api/v1/login/access-token', {
    method: 'POST',
    body: form,
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
}
