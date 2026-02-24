import { config } from '@/lib/config';

type ApiFetchOptions = RequestInit & {
  token?: string;
};

const API_BASE_URL = config.apiBaseUrl;

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function parseResponse(response: Response) {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export async function apiFetch<T>(
  path: string,
  init?: ApiFetchOptions,
): Promise<T> {
  const { token, headers, ...rest } = init ?? {};

  const url = `${API_BASE_URL}${path}`;

  const response = await fetch(url, {
    ...rest,
    headers: {
      ...(rest.body &&
      !(rest.body instanceof FormData) &&
      !(rest.body instanceof URLSearchParams)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...(headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: 'no-store',
  });

  const body = await parseResponse(response);

  if (!response.ok) {
    throw new ApiError(
      `Request failed: ${response.status} ${response.statusText}`,
      response.status,
      body,
    );
  }

  return body as T;
}
