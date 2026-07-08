'use client';

import { CommandCentreShell } from '@/features/shell/components';
import { ReportsPanel } from '@/features/reports/reports-panel';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export default function ReportsPage() {
  const runId = useWorkspaceUiStore((state) => state.activeRunId);

  return (
    <CommandCentreShell>
      {runId ? (
        <ReportsPanel runId={runId} />
      ) : (
        <ReportsPanel runId="run_01ARZ3NDEKTSV4RRFFQ69G5FAV" />
      )}
    </CommandCentreShell>
  );
}
