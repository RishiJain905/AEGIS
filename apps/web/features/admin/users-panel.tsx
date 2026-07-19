'use client';

import { Badge, DataTable, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';
import type { DataTableColumn } from '@aegis/ui';

import { useAdminUsers } from './use-admin-queries';
import type { AdminUser } from './types';

const columns: DataTableColumn<AdminUser & Record<string, unknown>>[] = [
  {
    key: 'displayName',
    header: 'Identity',
    render: (row) => (
      <div className="flex flex-col gap-0.5">
        <span className="font-medium text-[var(--aegis-text-primary)]">{row.displayName}</span>
        <code className="text-xs text-[var(--aegis-text-muted)]">{row.userId}</code>
      </div>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (row) => <Badge variant="outline">{row.status}</Badge>,
  },
  {
    key: 'roles',
    header: 'Roles',
    render: (row) => (
      <div className="flex flex-wrap gap-1.5">
        {row.roles.length > 0 ? (
          row.roles.map((role) => <Badge key={role}>{role}</Badge>)
        ) : (
          <span className="text-xs text-[var(--aegis-text-muted)]">none</span>
        )}
      </div>
    ),
  },
  {
    key: 'permissions',
    header: 'Effective permissions',
    render: (row) => (
      <span className="text-xs text-[var(--aegis-text-secondary)]">
        {row.permissions.length} granted
        {row.permissions.includes('admin:manage') ? ' · admin' : ''}
      </span>
    ),
  },
];

export function UsersPanel() {
  const query = useAdminUsers(true);

  return (
    <Panel
      title="Users & Roles"
      description="Authorized identities in the platform registry and the roles that grant their permissions."
    >
      {query.isPending ? (
        <LoadingState message="Loading identities" />
      ) : query.isError ? (
        <ErrorState
          title="Could not load users"
          message="The identity registry could not be read. Retry, or confirm the API is reachable."
          onRetry={() => void query.refetch()}
        />
      ) : query.data.users.length === 0 ? (
        <EmptyState
          title="No identities"
          description="No authorized identities are registered yet."
        />
      ) : (
        <div className="space-y-3" data-testid="admin-users">
          <p className="text-xs text-[var(--aegis-text-muted)]">
            {query.data.total} identit{query.data.total === 1 ? 'y' : 'ies'}
          </p>
          <DataTable
            columns={columns}
            data={query.data.users as (AdminUser & Record<string, unknown>)[]}
            caption="Authorized platform identities and their roles"
          />
        </div>
      )}
    </Panel>
  );
}
