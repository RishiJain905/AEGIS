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

  useEffect(() => {
    if (auth.isLoading || isPublic) {
      return;
    }
    if (!auth.isAuthenticated) {
      router.replace('/sign-in');
    }
  }, [auth.isAuthenticated, auth.isLoading, isPublic, router]);

  if (isPublic) {
    return children;
  }

  if (auth.isLoading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        data-testid="auth-gate-loading"
      >
        Verifying session…
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        data-testid="auth-gate-redirect"
      >
        Redirecting to sign-in…
      </div>
    );
  }

  return children;
}
