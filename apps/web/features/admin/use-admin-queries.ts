'use client';

import { useQuery } from '@tanstack/react-query';

import { apiFetchJson } from '@/lib/api/auth-fetch';

import type { AdminPolicyResponse, AdminSettingsResponse, AdminUsersResponse } from './types';

export const adminQueryKeys = {
  users: ['admin', 'users'] as const,
  policy: ['admin', 'policy'] as const,
  settings: ['admin', 'settings'] as const,
};

export function useAdminUsers(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.users,
    queryFn: ({ signal }) => apiFetchJson<AdminUsersResponse>('/api/v1/admin/users', { signal }),
    enabled,
  });
}

export function useAdminPolicy(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.policy,
    queryFn: ({ signal }) => apiFetchJson<AdminPolicyResponse>('/api/v1/admin/policy', { signal }),
    enabled,
  });
}

export function useAdminSettings(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.settings,
    queryFn: ({ signal }) =>
      apiFetchJson<AdminSettingsResponse>('/api/v1/admin/settings', { signal }),
    enabled,
  });
}
