import { config } from '@/lib/config';

import {
  clearAuthTokens,
  getRefreshToken,
  setAuthTokens,
} from './auth';

type ApiFetchOptions = RequestInit & {
  token?: string;
  skipAuthRefresh?: boolean;
};

const API_BASE_URL = config.apiBaseUrl;

type TokenResponse = {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
  expires_in?: number | null;
};

let refreshPromise: Promise<string> | null = null;

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

function joinApiUrl(baseUrl: string, path: string) {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${normalizedBaseUrl}${normalizedPath}`;
}

function buildRequestHeaders(
  headers: HeadersInit | undefined,
  body: BodyInit | null | undefined,
  token: string | undefined,
) {
  const requestHeaders = new Headers(headers);

  if (
    body &&
    !(body instanceof FormData) &&
    !(body instanceof URLSearchParams) &&
    !requestHeaders.has('Content-Type')
  ) {
    requestHeaders.set('Content-Type', 'application/json');
  }

  if (token) {
    requestHeaders.set('Authorization', `Bearer ${token}`);
  }

  return requestHeaders;
}

async function requestRefreshedAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  refreshPromise ??= fetch(joinApiUrl(API_BASE_URL, '/api/v1/login/refresh'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: 'no-store',
  })
    .then(async (response) => {
      const body = await parseResponse(response);

      if (!response.ok) {
        throw new ApiError(
          `Request failed: ${response.status} ${response.statusText}`,
          response.status,
          body,
        );
      }

      const data = body as TokenResponse;
      setAuthTokens(data.access_token, data.refresh_token ?? null);
      return data.access_token;
    })
    .catch((error) => {
      clearAuthTokens();
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

async function fetchWithToken(
  url: string,
  rest: RequestInit,
  headers: HeadersInit | undefined,
  token: string | undefined,
) {
  const response = await fetch(url, {
    ...rest,
    headers: buildRequestHeaders(headers, rest.body, token),
    cache: 'no-store',
  });
  const body = await parseResponse(response);

  return { body, response };
}

export async function apiFetch<T>(
  path: string,
  init?: ApiFetchOptions,
): Promise<T> {
  const { token, headers, skipAuthRefresh, ...rest } = init ?? {};

  const url = joinApiUrl(API_BASE_URL, path);

  const { body, response } = await fetchWithToken(url, rest, headers, token);

  if (!response.ok) {
    if (response.status === 401 && token && !skipAuthRefresh) {
      const refreshedToken = await requestRefreshedAccessToken().catch(() => null);

      if (refreshedToken) {
        const retry = await fetchWithToken(url, rest, headers, refreshedToken);
        if (retry.response.ok) {
          return retry.body as T;
        }

        throw new ApiError(
          `Request failed: ${retry.response.status} ${retry.response.statusText}`,
          retry.response.status,
          retry.body,
        );
      }
    }

    throw new ApiError(
      `Request failed: ${response.status} ${response.statusText}`,
      response.status,
      body,
    );
  }

  return body as T;
}
