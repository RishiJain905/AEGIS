import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { replace, devLogin, passwordLogin, createAdminAccount, apiFetchJson } = vi.hoisted(() => ({
  replace: vi.fn(),
  devLogin: vi.fn(),
  passwordLogin: vi.fn(),
  createAdminAccount: vi.fn(),
  apiFetchJson: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
}));

vi.mock('@/features/auth/auth-provider', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    devLogin,
    passwordLogin,
    createAdminAccount,
  }),
}));

vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetchJson,
}));

import { SignInPanel } from '@/features/auth/sign-in-panel';

/**
 * Route the single apiFetchJson mock by URL. `setupRequired` toggles the first-run
 * flow; `devUsers` is either a user array (dev auth enabled) or a rejection (403).
 */
function mockEndpoints(options: {
  setupRequired: boolean;
  devUsers?: { userId: string; displayName: string; roles: string[] }[] | 'forbidden';
}) {
  apiFetchJson.mockImplementation((url: string) => {
    if (url === '/api/v1/auth/setup-status') {
      return Promise.resolve({ setupRequired: options.setupRequired });
    }
    if (url === '/api/v1/auth/dev/users') {
      if (!options.devUsers || options.devUsers === 'forbidden') {
        return Promise.reject(new Error('Development authentication is disabled'));
      }
      return Promise.resolve({ users: options.devUsers });
    }
    return Promise.reject(new Error(`unexpected url ${url}`));
  });
}

describe('SignInPanel', () => {
  beforeEach(() => {
    apiFetchJson.mockReset();
    devLogin.mockReset();
    devLogin.mockResolvedValue(undefined);
    passwordLogin.mockReset();
    passwordLogin.mockResolvedValue(undefined);
    createAdminAccount.mockReset();
    createAdminAccount.mockResolvedValue(undefined);
    replace.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('shows the password login form when accounts already exist', async () => {
    mockEndpoints({ setupRequired: false, devUsers: 'forbidden' });
    render(<SignInPanel />);

    expect(await screen.findByTestId('sign-in-form')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    // No first-run setup fields.
    expect(screen.queryByTestId('sign-in-confirm-password')).not.toBeInTheDocument();
  });

  it('submits username/password credentials on login', async () => {
    mockEndpoints({ setupRequired: false, devUsers: 'forbidden' });
    render(<SignInPanel />);

    fireEvent.change(await screen.findByTestId('sign-in-username'), {
      target: { value: 'operator1' },
    });
    fireEvent.change(screen.getByTestId('sign-in-password'), {
      target: { value: 'sup3rsecretpass' },
    });
    fireEvent.click(screen.getByTestId('sign-in-submit'));

    await waitFor(() => {
      expect(passwordLogin).toHaveBeenCalledWith('operator1', 'sup3rsecretpass');
    });
  });

  it('renders the first-run create-admin form when no accounts exist', async () => {
    mockEndpoints({ setupRequired: true, devUsers: 'forbidden' });
    render(<SignInPanel />);

    expect(
      await screen.findByRole('heading', { name: 'Create admin account' }),
    ).toBeInTheDocument();
    expect(screen.getByTestId('sign-in-confirm-password')).toBeInTheDocument();
  });

  it('blocks admin creation when the passwords do not match', async () => {
    mockEndpoints({ setupRequired: true, devUsers: 'forbidden' });
    render(<SignInPanel />);

    fireEvent.change(await screen.findByTestId('sign-in-username'), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByTestId('sign-in-password'), {
      target: { value: 'longenoughpass1' },
    });
    fireEvent.change(screen.getByTestId('sign-in-confirm-password'), {
      target: { value: 'differentpass1' },
    });
    fireEvent.click(screen.getByTestId('sign-in-submit'));

    expect(await screen.findByTestId('sign-in-error')).toHaveTextContent('do not match');
    expect(createAdminAccount).not.toHaveBeenCalled();
  });

  it('creates the admin account when the setup form is valid', async () => {
    mockEndpoints({ setupRequired: true, devUsers: 'forbidden' });
    render(<SignInPanel />);

    fireEvent.change(await screen.findByTestId('sign-in-username'), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByTestId('sign-in-password'), {
      target: { value: 'longenoughpass1' },
    });
    fireEvent.change(screen.getByTestId('sign-in-confirm-password'), {
      target: { value: 'longenoughpass1' },
    });
    fireEvent.click(screen.getByTestId('sign-in-submit'));

    await waitFor(() => {
      expect(createAdminAccount).toHaveBeenCalledWith({
        username: 'admin',
        password: 'longenoughpass1',
        displayName: '',
      });
    });
  });

  it('hides the dev-identity picker when dev auth is disabled', async () => {
    mockEndpoints({ setupRequired: false, devUsers: 'forbidden' });
    render(<SignInPanel />);

    await screen.findByTestId('sign-in-form');
    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalledWith('/api/v1/auth/dev/users');
    });
    expect(screen.queryByTestId('dev-identity-picker')).not.toBeInTheDocument();
  });

  it('shows the dev-identity picker when dev auth is enabled', async () => {
    mockEndpoints({
      setupRequired: false,
      devUsers: [
        {
          userId: 'user:analyst',
          displayName: 'Alex Analyst',
          roles: ['analyst'],
        },
      ],
    });
    render(<SignInPanel />);

    expect(await screen.findByTestId('dev-identity-picker')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('dev-login-analyst'));
    await waitFor(() => {
      expect(devLogin).toHaveBeenCalledWith('user:analyst');
    });
  });
});
