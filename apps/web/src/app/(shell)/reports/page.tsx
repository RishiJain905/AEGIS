'use client';

import { CommandCentreShell } from '@/features/shell/components';
import { ReportsWorkspace } from '@/features/reports/reports-workspace';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

export default function ReportsPage() {
  const runId = useWorkspaceUiStore((state) => state.activeRunId);

  return (
    <CommandCentreShell>
      <ReportsWorkspace runId={runId ?? 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV'} />
    </CommandCentreShell>
  );
}
