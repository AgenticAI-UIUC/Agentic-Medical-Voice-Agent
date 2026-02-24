export function formatApiDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;

        if (item && typeof item === 'object') {
          // FastAPI validation errors often include "msg"
          if ('msg' in item) {
            return String((item as { msg?: unknown }).msg ?? 'Invalid input');
          }
        }

        try {
          return JSON.stringify(item);
        } catch {
          return 'Invalid input';
        }
      })
      .join('; ');
  }

  if (detail && typeof detail === 'object') {
    // Some APIs return { message: "..."} or other object shapes
    if ('message' in detail) {
      return String(
        (detail as { message?: unknown }).message ?? 'Request failed',
      );
    }

    try {
      return JSON.stringify(detail);
    } catch {
      return 'Request failed';
    }
  }

  return 'Request failed';
}
