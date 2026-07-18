import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { replace, devLogin, apiFetchJson } = vi.hoisted(() => ({
  replace: vi.fn(),
  devLogin: vi.fn(),
  apiFetchJson: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
}));

vi.mock('@/features/auth/auth-provider', () => ({
  useAuth: () => ({ isAuthenticated: false, devLogin }),
}));

vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetchJson,
}));

import { SignInPanel } from '@/features/auth/sign-in-panel';

const seedUsers = {
  users: [
    { userId: 'user:analyst', displayName: 'Alex Analyst', roles: ['ANALYST'] },
    { userId: 'user:commander', displayName: 'Casey Commander', roles: ['COMMANDER'] },
  ],
};

describe('SignInPanel dev-identity fetch', () => {
  beforeEach(() => {
    apiFetchJson.mockReset();
    devLogin.mockReset();
    devLogin.mockResolvedValue(undefined);
    replace.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders identities when the dev-users fetch succeeds', async () => {
    apiFetchJson.mockResolvedValue(seedUsers);
    render(<SignInPanel />);

    expect(await screen.findByTestId('dev-login-ANALYST')).toBeInTheDocument();
    expect(screen.getByText('Alex Analyst')).toBeInTheDocument();
    expect(screen.queryByTestId('sign-in-users-error')).not.toBeInTheDocument();
  });

  it('shows an error state with a retry action when the fetch fails', async () => {
    apiFetchJson.mockRejectedValue(new Error('network down'));
    render(<SignInPanel />);

    expect(await screen.findByTestId('sign-in-users-error')).toBeInTheDocument();
    expect(screen.getByTestId('sign-in-users-retry')).toBeInTheDocument();
    // The panel must not silently render an empty identity list.
    expect(screen.queryByTestId('dev-login-ANALYST')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sign-in-users-empty')).not.toBeInTheDocument();
  });

  it('recovers identities after the user clicks retry', async () => {
    apiFetchJson.mockRejectedValueOnce(new Error('network down')).mockResolvedValue(seedUsers);
    render(<SignInPanel />);

    const retry = await screen.findByTestId('sign-in-users-retry');
    fireEvent.click(retry);

    expect(await screen.findByTestId('dev-login-ANALYST')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByTestId('sign-in-users-error')).not.toBeInTheDocument();
    });
  });

  it('distinguishes an empty identity list from a fetch failure', async () => {
    apiFetchJson.mockResolvedValue({ users: [] });
    render(<SignInPanel />);

    expect(await screen.findByTestId('sign-in-users-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('sign-in-users-error')).not.toBeInTheDocument();
  });
});
