import { apiFetch } from './client';

export type HealthCheckResponse = {
  status: string;
};

export function getHealthCheck() {
  return apiFetch<HealthCheckResponse>('/health', {
    method: 'GET',
  });
}
