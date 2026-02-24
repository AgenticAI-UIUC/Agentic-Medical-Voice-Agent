import { ApiError } from '@/lib/api/client';
import { formatApiDetail } from '@/lib/api/errors';

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (
      typeof error.body === 'object' &&
      error.body !== null &&
      'detail' in error.body
    ) {
      return formatApiDetail((error.body as { detail?: unknown }).detail);
    }
    return error.message || fallback;
  }

  if (error instanceof Error) return error.message;
  return fallback;
}
