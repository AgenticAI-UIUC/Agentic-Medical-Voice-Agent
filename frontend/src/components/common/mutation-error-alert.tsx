import { ApiError } from '@/lib/api/client';
import { formatApiDetail } from '@/lib/api/errors';

type MutationErrorAlertProps = {
  error: unknown;
  fallbackMessage?: string;
};

function getErrorMessage(error: unknown, fallbackMessage: string) {
  if (error instanceof ApiError) {
    if (
      typeof error.body === 'object' &&
      error.body !== null &&
      'detail' in error.body
    ) {
      return formatApiDetail((error.body as { detail?: unknown }).detail);
    }
    return error.message || fallbackMessage;
  }

  if (error instanceof Error) return error.message;
  return fallbackMessage;
}

export function MutationErrorAlert({
  error,
  fallbackMessage = 'Something went wrong.',
}: MutationErrorAlertProps) {
  if (!error) return null;

  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
      {getErrorMessage(error, fallbackMessage)}
    </div>
  );
}
