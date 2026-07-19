'use client';

import { Badge, DataTable, ErrorState, LoadingState, Panel } from '@aegis/ui';
import type { DataTableColumn } from '@aegis/ui';

import { useAdminPolicy } from './use-admin-queries';
import type { AdminCommand, AdminRolePermissions } from './types';

// Permission chips shrink to the eyebrow scale with tighter horizontal padding
// so the densest table in the app wraps far less across its rows (spec §4.8).
const PERMISSION_CHIP_CLASS = 'min-h-5 px-1.5 py-0.5 tracking-[0.06em]';

const roleColumns: DataTableColumn<AdminRolePermissions & Record<string, unknown>>[] = [
  {
    key: 'role',
    header: 'Role',
    render: (row) => <Badge>{row.role}</Badge>,
  },
  {
    key: 'permissions',
    header: 'Permissions',
    render: (row) => (
      <div className="flex flex-wrap gap-1">
        {row.permissions.map((permission) => (
          <Badge key={permission} variant="outline" className={PERMISSION_CHIP_CLASS}>
            {permission}
          </Badge>
        ))}
      </div>
    ),
  },
];

const commandColumns: DataTableColumn<AdminCommand & Record<string, unknown>>[] = [
  {
    key: 'command',
    header: 'Command',
    render: (row) => <code className="text-xs">{row.command}</code>,
  },
  {
    key: 'actionClass',
    header: 'Action class',
    render: (row) => <Badge variant="outline">{row.actionClass}</Badge>,
  },
  {
    key: 'scenarioRestricted',
    header: 'Scenario-restricted',
    render: (row) =>
      row.scenarioRestricted ? (
        <Badge>restricted</Badge>
      ) : (
        <span className="text-xs text-[var(--aegis-text-muted)]">—</span>
      ),
  },
];

export function PolicyPanel() {
  const query = useAdminPolicy(true);

  return (
    <Panel
      title="Policy"
      density="compact"
      description="The permission-role matrix and action-class rules enforced server-side. This view is read-only — enforcement lives in the API policy engine, never the UI."
    >
      {query.isPending ? (
        <LoadingState message="Loading policy" />
      ) : query.isError ? (
        <ErrorState
          title="Could not load policy"
          message="The enforced policy could not be read. Retry, or confirm the API is reachable."
          onRetry={() => void query.refetch()}
        />
      ) : (
        <div className="space-y-6" data-testid="admin-policy">
          <Badge operationalStatus="empty" aria-label="Read only, enforced server-side">
            enforced server-side · read-only
          </Badge>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">
              Role → permission matrix
            </h3>
            <DataTable
              columns={roleColumns}
              data={query.data.roles as (AdminRolePermissions & Record<string, unknown>)[]}
              caption="Roles and the permissions they grant"
              zebra
            />
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">
              Action classes (0–3)
            </h3>
            <ul className="grid gap-2 sm:grid-cols-2">
              {query.data.actionClasses.map((entry) => (
                <li
                  key={entry.actionClass}
                  className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-[var(--aegis-text-primary)]">
                      {entry.label}
                    </span>
                    {entry.approvalRequired ? (
                      <Badge>approval required</Badge>
                    ) : (
                      <Badge variant="outline">auto-allowed</Badge>
                    )}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-[var(--aegis-text-secondary)]">
                    {entry.description}
                  </p>
                </li>
              ))}
            </ul>
            <p className="text-xs text-[var(--aegis-text-muted)]">
              Approver roles for gated actions: {query.data.approverRoles.join(', ')}
            </p>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-[var(--aegis-text-primary)]">
              Allowlisted scenario commands
            </h3>
            <DataTable
              columns={commandColumns}
              data={query.data.commands as (AdminCommand & Record<string, unknown>)[]}
              caption="Allowlisted commands and their action classes"
              zebra
            />
          </section>
        </div>
      )}
    </Panel>
  );
}
