'use client';

import { EmptyState, Panel } from '@aegis/ui';

import { CommandCentreShell } from '@/features/shell/components';

export default function ReportsPage() {
  return (
    <CommandCentreShell>
      <Panel title="Reports" description="After-action and evaluation reports — Phase 29">
        <EmptyState
          title="No reports generated"
          description="Report generation and scoring exports are deferred to later phases."
        />
      </Panel>
    </CommandCentreShell>
  );
}
