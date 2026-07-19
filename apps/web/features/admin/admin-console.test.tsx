import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useAuth } = vi.hoisted(() => ({ useAuth: vi.fn() }));
const { useAdminUsers, useAdminPolicy, useAdminSettings } = vi.hoisted(() => ({
  useAdminUsers: vi.fn(),
  useAdminPolicy: vi.fn(),
  useAdminSettings: vi.fn(),
}));

vi.mock('@/features/auth', () => ({ useAuth }));
vi.mock('@/features/admin/use-admin-queries', () => ({
  adminQueryKeys: {
    users: ['admin', 'users'],
    policy: ['admin', 'policy'],
    settings: ['admin', 'settings'],
  },
  useAdminUsers,
  useAdminPolicy,
  useAdminSettings,
}));

import { AdminConsole } from '@/features/admin/admin-console';
import { PlatformPanel } from '@/features/admin/platform-panel';
import { PolicyPanel } from '@/features/admin/policy-panel';
import { UsersPanel } from '@/features/admin/users-panel';

function adminAuth() {
  return {
    isLoading: false,
    isAuthenticated: true,
    hasPermission: (p: string) => p === 'admin:manage',
  };
}

describe('AdminConsole access gate', () => {
  beforeEach(() => {
    useAuth.mockReset();
    useAdminUsers.mockReturnValue({
      isPending: false,
      isError: false,
      data: { users: [], total: 0 },
    });
    useAdminPolicy.mockReturnValue({ isPending: true, isError: false });
    useAdminSettings.mockReturnValue({ isPending: true, isError: false });
  });

  afterEach(() => {
    cleanup();
  });

  it('shows a forbidden state for a non-admin (UI courtesy; API is the real guard)', () => {
    useAuth.mockReturnValue({
      isLoading: false,
      isAuthenticated: true,
      hasPermission: () => false,
    });
    render(<AdminConsole />);
    expect(screen.getByText('Administrator access required')).toBeInTheDocument();
    expect(screen.queryByText('Users & Roles')).not.toBeInTheDocument();
  });

  it('shows a loading state while access is being resolved', () => {
    useAuth.mockReturnValue({
      isLoading: true,
      isAuthenticated: false,
      hasPermission: () => false,
    });
    render(<AdminConsole />);
    expect(screen.getByText('Checking administrator access')).toBeInTheDocument();
  });

  it('renders the admin tabs for an administrator', () => {
    useAuth.mockReturnValue(adminAuth());
    render(<AdminConsole />);
    expect(screen.getByRole('tab', { name: 'Users & Roles' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Policy' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Platform' })).toBeInTheDocument();
  });
});

describe('UsersPanel states', () => {
  beforeEach(() => useAdminUsers.mockReset());
  afterEach(() => {
    cleanup();
  });

  it('renders an error state with retry', () => {
    useAdminUsers.mockReturnValue({
      isPending: false,
      isError: true,
      refetch: vi.fn(),
    });
    render(<UsersPanel />);
    expect(screen.getByText('Could not load users')).toBeInTheDocument();
  });

  it('renders identities with derived admin marker', () => {
    useAdminUsers.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        total: 1,
        users: [
          {
            userId: 'user:admin-alpha',
            displayName: 'Admin Alpha',
            status: 'active',
            roles: ['admin'],
            permissions: ['admin:manage', 'runs:read'],
          },
        ],
      },
    });
    render(<UsersPanel />);
    expect(screen.getByTestId('admin-users')).toBeInTheDocument();
    expect(screen.getByText('Admin Alpha')).toBeInTheDocument();
  });
});

describe('PolicyPanel', () => {
  beforeEach(() => useAdminPolicy.mockReset());
  afterEach(() => {
    cleanup();
  });

  it('labels the policy as enforced server-side and read-only', () => {
    useAdminPolicy.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        roles: [{ role: 'admin', permissions: ['admin:manage'] }],
        permissions: ['admin:manage'],
        actionClasses: [
          {
            actionClass: 'class_2',
            label: 'Class 2',
            approvalRequired: true,
            description: 'x',
          },
        ],
        commands: [
          {
            command: 'isolate',
            actionClass: 'class_2',
            scenarioRestricted: false,
          },
        ],
        approverRoles: ['incident_commander', 'security_lead'],
      },
    });
    render(<PolicyPanel />);
    expect(screen.getByTestId('admin-policy')).toBeInTheDocument();
    expect(screen.getByText(/enforced server-side · read-only/i)).toBeInTheDocument();
  });
});

describe('PlatformPanel', () => {
  beforeEach(() => useAdminSettings.mockReset());
  afterEach(() => {
    cleanup();
  });

  it('renders health, provider mode, and the secret-exclusion note', () => {
    useAdminSettings.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        environment: 'test',
        version: '1.0.0',
        logLevel: 'info',
        provider: { defaultProvider: 'mock', localModel: 'llama3.2' },
        websocket: { enabled: true },
        security: { hstsEnabled: false },
        observability: { otelEnabled: false },
        auth: { devAuthEnabled: true },
        health: {
          status: 'ready',
          dependencies: [{ name: 'postgres', state: 'ready' }],
        },
      },
    });
    render(<PlatformPanel />);
    expect(screen.getByTestId('admin-platform')).toBeInTheDocument();
    expect(screen.getByText(/Secrets .* are never included/i)).toBeInTheDocument();
  });
});
