import { apiFetch } from './client';

export type HealthCheckResponse = {
  status: string;
};

export function getHealthCheck() {
  return apiFetch<HealthCheckResponse>('/api/v1/utils/health-check', {
    method: 'GET',
  });
}
