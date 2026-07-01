'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import {
  Button,
  DataTable,
  DataTableContainer,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from '@aegis/ui';

import { CommandCentreShell } from '@/features/shell/components/command-centre-shell';
import { useRuns, useScenarios } from '@/features/shell/hooks/use-shell-queries';

const SILENT_RELAY_SCENARIO_ID = 'scenario:operation-silent-relay';
const SILENT_RELAY_VERSION_ID = 'scenario-version:1.0.0-silent-relay';
const SYNTHETIC_VERSION_ID = 'scenario-version:v1.0.0-synthetic';
const DEFAULT_SYNTHETIC_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function resolveRunId(
  scenarioId: string,
  runs: { id: string; scenarioVersionId: string }[] | undefined,
): string {
  if (!runs?.length) {
    return DEFAULT_SYNTHETIC_RUN_ID;
  }
  if (scenarioId === SILENT_RELAY_SCENARIO_ID) {
    const silentRelayRun = runs.find((run) => run.scenarioVersionId === SILENT_RELAY_VERSION_ID);
    if (silentRelayRun) {
      return silentRelayRun.id;
    }
  }
  const syntheticRun = runs.find((run) => run.scenarioVersionId === SYNTHETIC_VERSION_ID);
  return syntheticRun?.id ?? DEFAULT_SYNTHETIC_RUN_ID;
}

export default function ScenariosPage() {
  const router = useRouter();
  const scenariosQuery = useScenarios();
  const runsQuery = useRuns();

  return (
    <CommandCentreShell>
      <Panel title="Scenario selection" description="Choose a scenario to start or resume a run">
        {scenariosQuery.isPending || runsQuery.isPending ? (
          <LoadingState message="Loading scenarios…" />
        ) : null}
        {scenariosQuery.isError ? (
          <ErrorState
            data-testid="scenarios-error"
            message="Unable to load scenarios."
            onRetry={() => void scenariosQuery.refetch()}
          />
        ) : null}
        {scenariosQuery.isSuccess && scenariosQuery.data.length === 0 ? (
          <EmptyState
            data-testid="scenarios-empty"
            title="No scenarios available"
            description="Published scenarios will appear here when the simulation platform is connected."
          />
        ) : null}
        {scenariosQuery.isSuccess && scenariosQuery.data.length > 0 ? (
          <DataTableContainer className="mt-4">
            <DataTable
              caption="Available scenarios"
              data-testid="scenarios-table"
              columns={[
                { key: 'name', header: 'Name' },
                { key: 'id', header: 'ID' },
                {
                  key: 'actions',
                  header: 'Actions',
                  render: (row: { id: string }) => (
                    <Button
                      size="sm"
                      onClick={() => {
                        router.push(`/runs/${resolveRunId(row.id, runsQuery.data)}`);
                      }}
                    >
                      Open run
                    </Button>
                  ),
                },
              ]}
              data={scenariosQuery.data.map((scenario: { name: string; id: string }) => ({
                name: scenario.name,
                id: scenario.id,
                actions: scenario.id,
              }))}
            />
          </DataTableContainer>
        ) : null}
        <div className="mt-4">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/design-system">Design system showcase</Link>
          </Button>
        </div>
      </Panel>
    </CommandCentreShell>
  );
}
