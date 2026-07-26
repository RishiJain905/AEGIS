import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useAuth, usePathname, replace } = vi.hoisted(() => ({
  useAuth: vi.fn(),
  usePathname: vi.fn(),
  replace: vi.fn(),
}));

vi.mock('@/features/auth/auth-provider', () => ({ useAuth }));
vi.mock('next/navigation', () => ({
  usePathname,
  useRouter: () => ({ replace }),
}));

import { AuthGate } from '@/features/auth/auth-gate';
import type { SessionStatus } from '@/features/auth/auth-provider';

function authState(sessionStatus: SessionStatus) {
  return {
    sessionStatus,
    isLoading: sessionStatus === 'loading',
    isAuthenticated: sessionStatus === 'authenticated',
  };
}

function renderGate() {
  return render(
    <AuthGate>
      <div data-testid="protected">command centre</div>
    </AuthGate>,
  );
}

describe('AuthGate', () => {
  beforeEach(() => {
    usePathname.mockReturnValue('/runs/run_1');
    replace.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders the app for an authenticated session', () => {
    useAuth.mockReturnValue(authState('authenticated'));
    renderGate();
    expect(screen.getByTestId('protected')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('waits while the session is still loading', () => {
    useAuth.mockReturnValue(authState('loading'));
    renderGate();
    expect(screen.getByTestId('auth-gate-loading')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('redirects only on a definitive unauthenticated response', () => {
    useAuth.mockReturnValue(authState('unauthenticated'));
    renderGate();
    expect(screen.getByTestId('auth-gate-redirect')).toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith('/sign-in');
  });

  it('keeps rendering — and never redirects — when the session state is unknown', () => {
    useAuth.mockReturnValue(authState('unknown'));
    renderGate();
    expect(screen.getByTestId('protected')).toBeInTheDocument();
    expect(screen.queryByTestId('auth-gate-redirect')).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('leaves public paths alone', () => {
    usePathname.mockReturnValue('/sign-in');
    useAuth.mockReturnValue(authState('unauthenticated'));
    renderGate();
    expect(screen.getByTestId('protected')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
