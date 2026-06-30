'use client';

import { EmptyState, Panel } from '@aegis/ui';

import { CommandCentreShell } from '@/features/shell/components';

export default function AdminPage() {
  return (
    <CommandCentreShell>
      <Panel title="Administration" description="Platform administration placeholder">
        <EmptyState
          title="Admin tools unavailable"
          description="User management, policy configuration, and platform settings arrive in production-readiness phases."
        />
      </Panel>
    </CommandCentreShell>
  );
}
