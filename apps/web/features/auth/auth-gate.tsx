'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { useAuth } from '@/features/auth/auth-provider';

const PUBLIC_PATHS = new Set(['/sign-in', '/design-system']);

export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.has(pathname);

  // Only a definitive "you are not signed in" answer from the server may
  // redirect. A failed request (429, 5xx, network blip) leaves the session
  // unknown — bouncing on that logged operators out on every rate-limited
  // refresh.
  const isSignedOut = auth.sessionStatus === 'unauthenticated';

  useEffect(() => {
    if (isPublic || !isSignedOut) {
      return;
    }
    router.replace('/sign-in');
  }, [isSignedOut, isPublic, router]);

  if (isPublic) {
    return children;
  }

  if (auth.sessionStatus === 'loading') {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        data-testid="auth-gate-loading"
      >
        Verifying session…
      </div>
    );
  }

  if (isSignedOut) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        data-testid="auth-gate-redirect"
      >
        Redirecting to sign-in…
      </div>
    );
  }

  // 'authenticated' or 'unknown' — when the session state is unknown, keep the
  // app rendered rather than tearing it down over a transient failure.
  return children;
}
