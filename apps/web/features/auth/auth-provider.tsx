'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from 'react';

import {
  authSessionResponseSchema,
  parseContract,
  type AuthSessionResponseV1,
  type AuthenticatedActorV1,
  type PermissionV1,
} from '@aegis/contracts-ts';

import { apiFetchJson, setMemoryCsrfToken } from '@/lib/api/auth-fetch';

const AUTH_SESSION_KEY = ['auth', 'session'] as const;

interface AuthContextValue {
  session: AuthSessionResponseV1 | undefined;
  actor: AuthenticatedActorV1 | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  hasPermission: (permission: PermissionV1) => boolean;
  hasRole: (role: string) => boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  devLogin: (userId: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function rememberCsrf(session: AuthSessionResponseV1 | undefined): void {
  setMemoryCsrfToken(session?.session?.csrfToken ?? null);
}

async function fetchSession(): Promise<AuthSessionResponseV1> {
  const session = await apiFetchJson('/api/v1/auth/session', {}, (data) =>
    parseContract(authSessionResponseSchema, data),
  );
  rememberCsrf(session);
  return session;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: AUTH_SESSION_KEY,
    queryFn: fetchSession,
    staleTime: 30_000,
    retry: false,
  });

  const logoutMutation = useMutation({
    mutationFn: async () =>
      apiFetchJson('/api/v1/auth/logout', { method: 'POST' }, (data) =>
        parseContract(authSessionResponseSchema, data),
      ),
    onSuccess: async () => {
      setMemoryCsrfToken(null);
      queryClient.clear();
      await queryClient.invalidateQueries({ queryKey: AUTH_SESSION_KEY });
    },
  });

  const devLoginMutation = useMutation({
    mutationFn: async (userId: string) =>
      apiFetchJson(
        '/api/v1/auth/dev/login',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ schemaVersion: 1, userId }),
        },
        (data) => parseContract(authSessionResponseSchema, data),
      ),
    onSuccess: async (session) => {
      rememberCsrf(session);
      queryClient.setQueryData(AUTH_SESSION_KEY, session);
    },
  });

  const actor = sessionQuery.data?.actor ?? null;

  const hasPermission = useCallback(
    (permission: PermissionV1) => {
      if (!actor) {
        return false;
      }
      return actor.permissions.includes(permission);
    },
    [actor],
  );

  const hasRole = useCallback(
    (role: string) => {
      if (!actor) {
        return false;
      }
      return actor.roles.includes(role as AuthenticatedActorV1['roles'][number]);
    },
    [actor],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session: sessionQuery.data,
      actor,
      isLoading: sessionQuery.isLoading,
      isAuthenticated: Boolean(sessionQuery.data?.authenticated && actor),
      hasPermission,
      hasRole,
      refresh: async () => {
        await sessionQuery.refetch();
      },
      logout: async () => {
        await logoutMutation.mutateAsync();
      },
      devLogin: async (userId: string) => {
        await devLoginMutation.mutateAsync(userId);
      },
    }),
    [
      actor,
      hasPermission,
      hasRole,
      logoutMutation,
      devLoginMutation,
      sessionQuery,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
