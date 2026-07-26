'use client';

import { EmptyState, LoadingState } from '@aegis/ui';

import { CommandCentreShell } from '@/features/shell/components';
import { ReportsWorkspace } from '@/features/reports/reports-workspace';
import { useRuns } from '@/features/shell/hooks/use-shell-queries';

interface RunSummary {
  id: string;
  startedAt: string;
}

/**
 * The run this workspace reports on.
 *
 * It cannot come from the workspace store's `activeRunId`: mounting `CommandCentreShell`
 * without a run calls `resetForRun(null)`, which clears that value on the way in — so on
 * this page it is always null. The page previously fell back to a hardcoded fixture run
 * id, which meant `/reports` never showed the operator their own run. `GET /runs` is
 * owner-scoped server-side, so the caller's most recent run is the honest default.
 */
function latestRun(runs: RunSummary[] | undefined): RunSummary | undefined {
  if (!runs?.length) {
    return undefined;
  }
  return [...runs].sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
}

export default function ReportsPage() {
  const runsQuery = useRuns();
  const run = latestRun(runsQuery.data as RunSummary[] | undefined);

  return (
    <CommandCentreShell>
      {runsQuery.isPending ? <LoadingState message="Loading reports…" /> : null}
      {!runsQuery.isPending && !run ? (
        <EmptyState
          data-testid="reports-no-run"
          title="No run to report on"
          description="After-action reports are generated per run. Launch an operation from the catalogue, and its SCRIBE report will appear here once the run completes."
        />
      ) : null}
      {run ? <ReportsWorkspace runId={run.id} /> : null}
    </CommandCentreShell>
  );
}
