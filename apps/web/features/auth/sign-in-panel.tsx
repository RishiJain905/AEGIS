'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { Alert, Button } from '@aegis/ui';

import { useAuth } from '@/features/auth/auth-provider';
import { apiFetchJson } from '@/lib/api/auth-fetch';

interface DevUser {
  userId: string;
  displayName: string;
  roles: string[];
}

type SetupStatus = 'loading' | 'setup' | 'login';

const inputClassName =
  'w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-strong)] bg-[var(--aegis-surface-base)] px-3 py-2.5 text-sm text-[var(--aegis-text-primary)] outline-none transition focus:border-[var(--aegis-accent-strong)] focus:ring-2 focus:ring-[var(--aegis-accent-line)]';
const labelClassName =
  'mb-1.5 block font-mono text-[0.625rem] uppercase tracking-[0.14em] text-[var(--aegis-text-muted)]';

export function SignInPanel() {
  const auth = useAuth();
  const router = useRouter();

  const [status, setStatus] = useState<SetupStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Credential form state.
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  // Development identity picker (only present when dev auth is enabled server-side).
  const [devUsers, setDevUsers] = useState<DevUser[]>([]);
  const [busyDevUserId, setBusyDevUserId] = useState<string | null>(null);

  useEffect(() => {
    if (auth.isAuthenticated) {
      router.replace('/');
    }
  }, [auth.isAuthenticated, router]);

  const loadSetupStatus = useCallback(async () => {
    setStatus('loading');
    try {
      const payload = await apiFetchJson<{ setupRequired: boolean }>('/api/v1/auth/setup-status');
      setStatus(payload.setupRequired ? 'setup' : 'login');
    } catch {
      // If we cannot determine setup state, fall back to the login form (fail closed
      // toward requiring credentials rather than exposing the setup flow).
      setStatus('login');
    }
  }, []);

  const loadDevUsers = useCallback(async () => {
    try {
      const payload = await apiFetchJson<{ users: DevUser[] }>('/api/v1/auth/dev/users');
      setDevUsers(payload.users);
    } catch {
      // 403 when dev auth is disabled (the fresh/prod experience) — hide the picker.
      setDevUsers([]);
    }
  }, []);

  useEffect(() => {
    void loadSetupStatus();
    void loadDevUsers();
  }, [loadSetupStatus, loadDevUsers]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (status === 'setup') {
      if (password !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
    }
    setBusy(true);
    try {
      if (status === 'setup') {
        await auth.createAdminAccount({ username, password, displayName });
      } else {
        await auth.passwordLogin(username, password);
      }
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setBusy(false);
    }
  };

  const onDevLogin = async (userId: string) => {
    setError(null);
    setBusyDevUserId(userId);
    try {
      await auth.devLogin(userId);
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setBusyDevUserId(null);
    }
  };

  const isSetup = status === 'setup';

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
              {isSetup ? 'First-run setup' : 'Identity checkpoint'}
            </p>
            <h2 className="text-2xl font-semibold tracking-tight">
              {isSetup ? 'Create admin account' : 'Sign in'}
            </h2>
            <p className="text-sm leading-6 text-[var(--aegis-text-secondary)]">
              {isSetup
                ? 'No accounts exist yet. Create the initial administrator to secure this deployment. This setup step closes automatically once the first account is created.'
                : 'Enter your username and password to access the command workspace.'}
            </p>
          </div>

          {error ? (
            <Alert variant="error" data-testid="sign-in-error">
              {error}
            </Alert>
          ) : null}

          {status === 'loading' ? (
            <p
              role="status"
              className="pt-2 text-sm text-[var(--aegis-text-secondary)]"
              data-testid="sign-in-loading"
            >
              Preparing sign-in…
            </p>
          ) : (
            <form
              className="space-y-4"
              onSubmit={(event) => void onSubmit(event)}
              data-testid="sign-in-form"
            >
              <div>
                <label className={labelClassName} htmlFor="aegis-username">
                  Username
                </label>
                <input
                  id="aegis-username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  className={inputClassName}
                  value={username}
                  onChange={(event) => {
                    setUsername(event.target.value);
                  }}
                  required
                  data-testid="sign-in-username"
                />
              </div>

              {isSetup ? (
                <div>
                  <label className={labelClassName} htmlFor="aegis-display-name">
                    Display name{' '}
                    <span className="normal-case text-[var(--aegis-text-muted)]">(optional)</span>
                  </label>
                  <input
                    id="aegis-display-name"
                    name="displayName"
                    type="text"
                    autoComplete="name"
                    className={inputClassName}
                    value={displayName}
                    onChange={(event) => {
                      setDisplayName(event.target.value);
                    }}
                    data-testid="sign-in-display-name"
                  />
                </div>
              ) : null}

              <div>
                <label className={labelClassName} htmlFor="aegis-password">
                  Password
                </label>
                <input
                  id="aegis-password"
                  name="password"
                  type="password"
                  autoComplete={isSetup ? 'new-password' : 'current-password'}
                  className={inputClassName}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                  }}
                  required
                  minLength={isSetup ? 12 : undefined}
                  data-testid="sign-in-password"
                />
                {isSetup ? (
                  <p className="mt-1.5 text-xs text-[var(--aegis-text-muted)]">
                    Minimum 12 characters, with at least one letter and one non-letter.
                  </p>
                ) : null}
              </div>

              {isSetup ? (
                <div>
                  <label className={labelClassName} htmlFor="aegis-confirm-password">
                    Confirm password
                  </label>
                  <input
                    id="aegis-confirm-password"
                    name="confirmPassword"
                    type="password"
                    autoComplete="new-password"
                    className={inputClassName}
                    value={confirmPassword}
                    onChange={(event) => {
                      setConfirmPassword(event.target.value);
                    }}
                    required
                    data-testid="sign-in-confirm-password"
                  />
                </div>
              ) : null}

              <Button
                type="submit"
                variant="default"
                className="w-full"
                disabled={busy}
                data-testid="sign-in-submit"
              >
                {busy
                  ? isSetup
                    ? 'Creating account…'
                    : 'Signing in…'
                  : isSetup
                    ? 'Create admin account'
                    : 'Sign in'}
              </Button>
            </form>
          )}

          {devUsers.length > 0 ? (
            <section
              className="space-y-3 border-t border-[var(--aegis-border-subtle)] pt-5"
              aria-label="Development identities"
              data-testid="dev-identity-picker"
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold">Development identities</h3>
                <span className="rounded-full border border-[var(--aegis-status-suspicious)]/40 bg-[var(--aegis-status-suspicious-bg)] px-2 py-1 font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--aegis-status-suspicious)]">
                  Local only
                </span>
              </div>
              <p className="text-xs leading-5 text-[var(--aegis-text-secondary)]">
                Passwordless local identities. Disabled and fail-closed in production.
              </p>
              <ul className="space-y-2 pt-1">
                {devUsers.map((user) => (
                  <li key={user.userId}>
                    <Button
                      variant="secondary"
                      className="h-auto min-h-12 w-full justify-between px-4 py-2.5"
                      data-testid={`dev-login-${user.roles[0] ?? 'user'}`}
                      disabled={busyDevUserId !== null}
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
            </section>
          ) : null}
        </div>
      </div>
    </main>
  );
}
