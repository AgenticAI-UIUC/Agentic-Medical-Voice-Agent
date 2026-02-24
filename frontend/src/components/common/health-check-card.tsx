'use client';

import { useQuery } from '@tanstack/react-query';

import { config } from '@/lib/config';
import { getHealthCheck } from '@/lib/api/health';

export function HealthCheckCard() {
  const query = useQuery({
    queryKey: ['health-check'],
    queryFn: getHealthCheck,
  });

  return (
    <div className="rounded-xl border p-4 shadow-sm">
      <h2 className="text-lg font-semibold">Backend Health Check</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Calls <code>/api/v1/utils/health-check</code> on your FastAPI backend
      </p>

      <div className="mt-4">
        {query.isPending && <p>Loading...</p>}

        {query.isError && (
          <div className="space-y-2 text-sm">
            <p className="text-red-600">Failed to reach backend.</p>
            <pre className="overflow-auto rounded bg-muted p-2 text-xs">
              {query.error instanceof Error
                ? query.error.message
                : 'Unknown error'}
            </pre>
            <p className="text-muted-foreground">
              Check backend is running and CORS allows{' '}
              <code>{typeof window !== 'undefined' ? window.location.origin : config.appName}</code>.
            </p>
          </div>
        )}

        {query.isSuccess && (
          <div className="space-y-1 text-sm">
            <p>
              Status:{' '}
              <span className="font-medium text-green-600">
                {query.data.status}
              </span>
            </p>
            <p className="text-muted-foreground">
              Frontend ↔ Backend connection is working.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
