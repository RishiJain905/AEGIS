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
  'w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-strong)] bg-[color-mix(in_srgb,var(--aegis-surface-base)_55%,transparent)] px-3.5 py-2.5 text-sm text-[var(--aegis-text-primary)] outline-none transition placeholder:text-[var(--aegis-text-faint)] focus:border-[var(--aegis-accent-line)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--aegis-focus-ring)_38%,transparent)]';
const labelClassName =
  'mb-2 block font-mono text-[0.625rem] font-medium uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]';

// CSS-only staggered entrance. Durations come from the shared motion tokens,
// which motion.css already collapses to ~0ms under prefers-reduced-motion; we
// additionally zero the per-item delays there so no content sits invisible
// during a delay window for reduced-motion users.
const revealStyles = `
@keyframes aegis-signin-reveal {
  from { opacity: 0; transform: translateY(14px) scale(0.99); }
  to { opacity: 1; transform: none; }
}
.aegis-signin-reveal {
  animation: aegis-signin-reveal var(--aegis-motion-duration-slow) var(--aegis-motion-ease-decelerate) both;
}
@media (prefers-reduced-motion: reduce) {
  .aegis-signin-reveal { animation-delay: 0ms !important; }
}
`;

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
      // Mirror server policy (apps/api/.../passwords.py) so setup failures are
      // actionable before the round-trip. Server remains authoritative.
      if (password.length < 12) {
        setError('Password must be at least 12 characters.');
        return;
      }
      const hasLetter = /[A-Za-z]/.test(password);
      const hasNonLetter = /[^A-Za-z]/.test(password);
      if (!hasLetter || !hasNonLetter) {
        setError('Password must include at least one letter and one non-letter character.');
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
      className="aegis-command-shell relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12 text-[var(--aegis-text-primary)] sm:px-6"
      data-testid="sign-in-page"
    >
      <style dangerouslySetInnerHTML={{ __html: revealStyles }} />

      {/* Ambient atmosphere: a warm horizon glow low on the field plus a soft
          spotlight lifting the card off the near-black canvas. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute inset-x-0 bottom-0 h-2/3"
          style={{
            background:
              'radial-gradient(ellipse 62rem 24rem at 50% 118%, color-mix(in srgb, var(--aegis-accent-cyan) 16%, transparent), transparent 72%)',
          }}
        />
        <div
          className="absolute left-1/2 top-1/2 h-[42rem] w-[42rem] -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            background:
              'radial-gradient(circle at center, color-mix(in srgb, var(--aegis-accent-cyan) 7%, transparent), transparent 68%)',
          }}
        />
      </div>

      <div className="relative flex w-full max-w-md flex-col gap-8">
        {/* Brand moment — oversized wordmark, thin gold rule, quiet mono tagline. */}
        <header className="flex flex-col gap-4">
          <p
            className="aegis-signin-reveal font-mono text-[0.6875rem] uppercase tracking-[0.32em] text-[var(--aegis-text-muted)]"
            style={{ animationDelay: '0ms' }}
          >
            Secure command access
          </p>
          <div
            className="aegis-signin-reveal flex items-end gap-3"
            style={{ animationDelay: '80ms' }}
          >
            <h1 className="font-[family-name:var(--aegis-font-display)] text-6xl font-bold leading-[0.85] tracking-[-0.04em] text-[var(--aegis-text-primary)] sm:text-7xl">
              AEGIS
            </h1>
            <span
              aria-hidden="true"
              className="mb-2 h-2 w-2 rounded-full bg-[var(--aegis-accent-cyan)] shadow-[0_0_18px_var(--aegis-accent-cyan)]"
            />
          </div>
          <div
            className="aegis-signin-reveal flex flex-col gap-3"
            style={{ animationDelay: '150ms' }}
          >
            <div
              aria-hidden="true"
              className="h-px w-full max-w-[13rem] bg-[linear-gradient(90deg,var(--aegis-accent-cyan),transparent)]"
            />
            <p className="font-mono text-[0.6875rem] uppercase tracking-[0.22em] text-[var(--aegis-text-muted)]">
              Cyber-defence command centre
            </p>
          </div>
        </header>

        {/* Floating frosted-glass card. */}
        <div
          className="aegis-signin-reveal relative overflow-hidden rounded-[var(--aegis-radius-xl)] border border-[var(--aegis-border-highlight)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_74%,transparent)] p-6 shadow-[var(--aegis-shadow-dialog)] backdrop-blur-xl sm:p-8"
          style={{ animationDelay: '230ms' }}
        >
          <div
            aria-hidden="true"
            className="absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,color-mix(in_srgb,var(--aegis-accent-cyan)_55%,transparent),transparent)]"
          />

          <div className="space-y-6">
            <div className="space-y-2">
              <p className="font-mono text-[0.6875rem] uppercase tracking-[0.18em] text-[var(--aegis-text-muted)]">
                {isSetup ? 'First-run setup' : 'Identity checkpoint'}
              </p>
              <h2 className="text-2xl font-semibold tracking-[-0.01em]">
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
                className="flex items-center gap-2 pt-1 text-sm text-[var(--aegis-text-secondary)]"
                data-testid="sign-in-loading"
              >
                <span
                  aria-hidden="true"
                  className="aegis-motion-pulse h-1.5 w-1.5 rounded-full bg-[var(--aegis-accent-cyan)]"
                />
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
                  size="lg"
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
                  <h3 className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]">
                    Development identities
                  </h3>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--aegis-status-suspicious)]/50 bg-[var(--aegis-status-suspicious-bg)] px-2.5 py-1 font-mono text-[0.625rem] font-semibold uppercase leading-none tracking-[0.12em] text-[var(--aegis-status-suspicious)]">
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 rounded-full bg-[var(--aegis-status-suspicious)]"
                    />
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

            <p className="border-t border-[var(--aegis-border-subtle)] pt-4 text-center font-mono text-[0.625rem] uppercase tracking-[0.14em] text-[var(--aegis-text-muted)]">
              Session-bound · Server enforced · Auditable
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
