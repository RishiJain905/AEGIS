'use client';

import { useQuery } from '@tanstack/react-query';

import { operatorProfileSchema, type OperatorProfileV1 } from '@aegis/contracts-ts';

import { apiFetchJson } from '@/lib/api/auth-fetch';

/**
 * Fetch the caller's cross-run operator skill-telemetry profile. Owner-scoped server-side; this
 * always requests the caller's own profile (no userId param), so a non-admin only ever sees
 * their own data.
 */
export function useOperatorProfile(options?: { enabled?: boolean }) {
  return useQuery<OperatorProfileV1>({
    queryKey: ['operator-profile'],
    queryFn: async ({ signal }) => {
      const body = await apiFetchJson<unknown>('/api/v1/profile/operator', { signal });
      return operatorProfileSchema.parse(body);
    },
    enabled: options?.enabled ?? true,
    staleTime: 60_000,
  });
}
