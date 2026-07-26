'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';

import {
  ContractValidationError,
  authSessionResponseSchema,
  parseContract,
  type AuthSessionResponseV1,
  type AuthenticatedActorV1,
  type PermissionV1,
} from '@aegis/contracts-ts';

import { ApiClientError } from '@/lib/api';
import { apiFetchJson, setMemoryCsrfToken } from '@/lib/api/auth-fetch';

const AUTH_SESSION_KEY = ['auth', 'session'] as const;
const MAX_SESSION_RETRIES = 4;

/**
 * Whether the session is known to be signed in, known to be signed out, or
 * simply unknown because the request never produced an answer. Only a definite
 * `unauthenticated` may bounce an operator to the sign-in page — a 429 or a
 * network blip must not.
 */
export type SessionStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'unknown';

/** A 401/403 is the server's answer, not a failed request. */
function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiClientError && (error.status === 401 || error.status === 403);
}

function shouldRetrySession(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_SESSION_RETRIES) {
    return false;
  }
  if (error instanceof ContractValidationError) {
    // A schema mismatch is deterministic; retrying only burns rate limit.
    return false;
  }
  if (error instanceof ApiClientError) {
    if (isUnauthorizedError(error)) {
      return false;
    }
    return error.status === 429 || error.status >= 500;
  }
  // No response reached us at all (network/CORS/abort): the session state is
  // unknown, so keep trying rather than declaring the operator signed out.
  return true;
}

function sessionRetryDelayMs(attemptIndex: number): number {
  return Math.min(30_000, 500 * 2 ** attemptIndex);
}

interface AuthContextValue {
  session: AuthSessionResponseV1 | undefined;
  actor: AuthenticatedActorV1 | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  sessionStatus: SessionStatus;
  hasPermission: (permission: PermissionV1) => boolean;
  hasRole: (role: string) => boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  devLogin: (userId: string) => Promise<void>;
  passwordLogin: (username: string, password: string) => Promise<void>;
  createAdminAccount: (input: {
    username: string;
    password: string;
    displayName: string;
  }) => Promise<void>;
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
    retry: shouldRetrySession,
    retryDelay: sessionRetryDelayMs,
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
    onSuccess: (session) => {
      rememberCsrf(session);
      queryClient.setQueryData(AUTH_SESSION_KEY, session);
    },
  });

  const passwordLoginMutation = useMutation({
    mutationFn: async (input: { username: string; password: string }) =>
      apiFetchJson(
        '/api/v1/auth/login',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ schemaVersion: 1, ...input }),
        },
        (data) => parseContract(authSessionResponseSchema, data),
      ),
    onSuccess: (session) => {
      rememberCsrf(session);
      queryClient.setQueryData(AUTH_SESSION_KEY, session);
    },
  });

  const createAdminMutation = useMutation({
    mutationFn: async (input: { username: string; password: string; displayName: string }) =>
      apiFetchJson(
        '/api/v1/auth/setup',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ schemaVersion: 1, ...input }),
        },
        (data) => parseContract(authSessionResponseSchema, data),
      ),
    onSuccess: (session) => {
      rememberCsrf(session);
      queryClient.setQueryData(AUTH_SESSION_KEY, session);
    },
  });

  const actor = sessionQuery.data?.actor ?? null;
  const isAuthenticated = Boolean(sessionQuery.data?.authenticated && actor);

  const sessionStatus = ((): SessionStatus => {
    // A previously loaded session outranks a failed refetch.
    if (sessionQuery.data) {
      return isAuthenticated ? 'authenticated' : 'unauthenticated';
    }
    if (isUnauthorizedError(sessionQuery.error)) {
      return 'unauthenticated';
    }
    if (sessionQuery.isLoading) {
      return 'loading';
    }
    return sessionQuery.isError ? 'unknown' : 'loading';
  })();

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
      isAuthenticated,
      sessionStatus,
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
      passwordLogin: async (username: string, password: string) => {
        await passwordLoginMutation.mutateAsync({ username, password });
      },
      createAdminAccount: async (input) => {
        await createAdminMutation.mutateAsync(input);
      },
    }),
    [
      actor,
      isAuthenticated,
      sessionStatus,
      hasPermission,
      hasRole,
      logoutMutation,
      devLoginMutation,
      passwordLoginMutation,
      createAdminMutation,
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
