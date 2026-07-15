'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Alert, Button } from '@aegis/ui';

import { useAuth } from '@/features/auth/auth-provider';
import { apiFetchJson } from '@/lib/api/auth-fetch';

interface DevUser {
  userId: string;
  displayName: string;
  roles: string[];
}

export function SignInPanel() {
  const auth = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<DevUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  useEffect(() => {
    if (auth.isAuthenticated) {
      router.replace('/');
    }
  }, [auth.isAuthenticated, router]);

  useEffect(() => {
    void apiFetchJson<{ users: DevUser[] }>('/api/v1/auth/dev/users')
      .then((payload) => setUsers(payload.users))
      .catch(() => {
        setUsers([]);
      });
  }, []);

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
      className="flex min-h-screen flex-col items-center justify-center bg-[radial-gradient(circle_at_top,#1b2a3a,#0b1118)] px-4 py-10 text-[var(--aegis-text-primary)]"
      data-testid="sign-in-page"
    >
      <div className="w-full max-w-lg space-y-6">
        <div className="space-y-2 text-center">
          <p className="font-mono text-xs tracking-[0.2em] text-[var(--aegis-text-secondary)]">
            AEGIS COMMAND CENTRE
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">Sign in</h1>
          <p className="text-sm text-[var(--aegis-text-secondary)]">
            Authentication determines who you are. Authorization determines what you may do.
            Server-side session cookies enforce both.
          </p>
        </div>

        {error ? (
          <Alert variant="error" data-testid="sign-in-error">
            {error}
          </Alert>
        ) : null}

        <section
          className="space-y-3 rounded-lg border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-elevated)]/80 p-4"
          aria-label="Development identities"
        >
          <h2 className="text-sm font-medium">Development identities</h2>
          <p className="text-xs text-[var(--aegis-text-secondary)]">
            Explicit local auth only. Disabled and fail-closed in production.
          </p>
          <ul className="space-y-2">
            {users.map((user) => (
              <li key={user.userId}>
                <Button
                  className="w-full justify-between"
                  data-testid={`dev-login-${user.roles[0] ?? 'user'}`}
                  disabled={busyUserId !== null}
                  onClick={() => void onDevLogin(user.userId)}
                >
                  <span>{user.displayName}</span>
                  <span className="font-mono text-xs opacity-80">{user.roles.join(', ')}</span>
                </Button>
              </li>
            ))}
          </ul>
        </section>

        <p className="text-center text-xs text-[var(--aegis-text-secondary)]">
          Production deployments use OIDC authorization-code flow via{' '}
          <code className="font-mono">/api/v1/auth/login</code>.{' '}
          <Link className="underline" href="/api/v1/auth/login">
            Continue with OIDC
          </Link>
        </p>
      </div>
    </main>
  );
}
