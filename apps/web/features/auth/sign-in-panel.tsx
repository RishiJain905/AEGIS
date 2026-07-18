'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Button } from '@aegis/ui';

import { useAuth } from '@/features/auth/auth-provider';
import { apiFetchJson } from '@/lib/api/auth-fetch';

interface DevUser {
  userId: string;
  displayName: string;
  roles: string[];
}

type UsersStatus = 'loading' | 'ready' | 'error';

export function SignInPanel() {
  const auth = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<DevUser[]>([]);
  const [usersStatus, setUsersStatus] = useState<UsersStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  useEffect(() => {
    if (auth.isAuthenticated) {
      router.replace('/');
    }
  }, [auth.isAuthenticated, router]);

  const loadUsers = useCallback(async () => {
    setUsersStatus('loading');
    try {
      const payload = await apiFetchJson<{ users: DevUser[] }>('/api/v1/auth/dev/users');
      setUsers(payload.users);
      setUsersStatus('ready');
    } catch {
      setUsers([]);
      setUsersStatus('error');
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const onDevLogin = async (userId: string) => {
    setError(null);
    setBusyUserId(userId);
    try {
      await auth.devLogin(userId);
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setBusyUserId(null);
    }
  };

  return (
    <main
      className="relative isolate flex min-h-screen items-center justify-center overflow-hidden bg-[var(--aegis-surface-base)] px-4 py-10 text-[var(--aegis-text-primary)] before:absolute before:inset-0 before:-z-10 before:bg-[linear-gradient(rgb(89_201_234_/_0.035)_1px,transparent_1px),linear-gradient(90deg,rgb(89_201_234_/_0.035)_1px,transparent_1px),radial-gradient(circle_at_22%_28%,rgb(34_111_139_/_0.25),transparent_30rem)] before:bg-[size:32px_32px,32px_32px,auto]"
      data-testid="sign-in-page"
    >
      <div className="grid w-full max-w-4xl overflow-hidden rounded-[var(--aegis-radius-xl)] border border-[var(--aegis-border-strong)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-dialog)] md:grid-cols-[0.9fr_1.1fr]">
        <section className="relative flex min-h-64 flex-col justify-between overflow-hidden border-b border-[var(--aegis-border-default)] bg-[radial-gradient(circle_at_30%_20%,rgb(40_126_157_/_0.25),transparent_18rem),linear-gradient(145deg,var(--aegis-surface-raised),var(--aegis-surface-rail))] p-7 md:min-h-[34rem] md:border-b-0 md:border-r">
          <div>
            <div className="mb-7 flex h-12 w-12 items-center justify-center rounded-[var(--aegis-radius-md)] border border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] font-[family-name:var(--aegis-font-display)] text-lg font-bold tracking-[0.12em] text-[var(--aegis-accent-strong)] shadow-[0_0_30px_rgb(89_201_234_/_0.12)]">
              A
            </div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-[var(--aegis-accent-cyan)]">
              AEGIS Command
            </p>
            <h1 className="mt-3 max-w-xs text-3xl font-semibold leading-tight tracking-[-0.025em]">
              Defensive operations, in one field of view.
            </h1>
            <p className="mt-4 max-w-sm text-sm leading-6 text-[var(--aegis-text-secondary)]">
              Authenticate to enter the protected command workspace and resume live investigation
              state.
            </p>
          </div>
          <div className="mt-8 border-l-2 border-[var(--aegis-status-normal)] pl-3">
            <p className="font-mono text-[0.625rem] uppercase tracking-[0.14em] text-[var(--aegis-text-muted)]">
              Access plane
            </p>
            <p className="mt-1 text-xs text-[var(--aegis-text-secondary)]">
              Session-bound · server enforced · auditable
            </p>
          </div>
        </section>

        <div className="space-y-6 p-6 sm:p-8 md:p-10">
          <div className="space-y-2">
            <p className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]">
              Identity checkpoint
            </p>
            <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
            <p className="text-sm leading-6 text-[var(--aegis-text-secondary)]">
              Choose an authorized local identity for this development environment.
            </p>
          </div>

          {error ? (
            <Alert variant="error" data-testid="sign-in-error">
              {error}
            </Alert>
          ) : null}

          <section className="space-y-3" aria-label="Development identities">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">Development identities</h3>
              <span className="rounded-full border border-[var(--aegis-status-suspicious)]/40 bg-[var(--aegis-status-suspicious-bg)] px-2 py-1 font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--aegis-status-suspicious)]">
                Local only
              </span>
            </div>
            <p className="text-xs leading-5 text-[var(--aegis-text-secondary)]">
              Explicit local auth is disabled and fail-closed in production.
            </p>

            {usersStatus === 'loading' ? (
              <p
                role="status"
                className="pt-2 text-sm text-[var(--aegis-text-secondary)]"
                data-testid="sign-in-users-loading"
              >
                Loading development identities…
              </p>
            ) : null}

            {usersStatus === 'error' ? (
              <div className="space-y-3 pt-2" data-testid="sign-in-users-error">
                <Alert variant="error">
                  Could not load development identities. The API may still be starting up.
                </Alert>
                <Button
                  variant="secondary"
                  className="w-full"
                  data-testid="sign-in-users-retry"
                  onClick={() => void loadUsers()}
                >
                  Retry
                </Button>
              </div>
            ) : null}

            {usersStatus === 'ready' && users.length === 0 ? (
              <p
                className="pt-2 text-sm text-[var(--aegis-text-secondary)]"
                data-testid="sign-in-users-empty"
              >
                No development identities are available. Confirm the API has seeded local
                identities.
              </p>
            ) : null}

            {usersStatus === 'ready' && users.length > 0 ? (
              <ul className="space-y-2 pt-2">
                {users.map((user) => (
                  <li key={user.userId}>
                    <Button
                      variant="secondary"
                      className="h-auto min-h-12 w-full justify-between px-4 py-2.5"
                      data-testid={`dev-login-${user.roles[0] ?? 'user'}`}
                      disabled={busyUserId !== null}
                      onClick={() => void onDevLogin(user.userId)}
                    >
                      <span className="text-left">{user.displayName}</span>
                      <span className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--aegis-text-muted)]">
                        {user.roles.join(', ')}
                      </span>
                    </Button>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <p className="border-t border-[var(--aegis-border-subtle)] pt-5 text-xs leading-5 text-[var(--aegis-text-secondary)]">
            Production deployments use OIDC authorization-code flow via{' '}
            <code className="rounded bg-[var(--aegis-surface-elevated)] px-1.5 py-0.5 font-mono">
              /api/v1/auth/login
            </code>
            .{' '}
            <Link
              className="font-semibold text-[var(--aegis-accent-strong)] underline decoration-[var(--aegis-accent-line)] underline-offset-4"
              href="/api/v1/auth/login"
              prefetch={false}
            >
              Continue with OIDC
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
