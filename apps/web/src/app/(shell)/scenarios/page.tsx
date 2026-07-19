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
import { useCreateRun } from '@/features/live-run';
import { useRuns, useScenarios } from '@/features/shell/hooks/use-shell-queries';

// Demo/admin owner assigned to seeded/legacy runs by migration 014. Runs owned by this
// identity are surfaced as demo/fixture data, not an ordinary result. See ADR 0034.
const DEMO_OWNER_USER_ID = 'user:admin-alpha';

interface ScenarioLaunchConfig {
  packagePath: string;
  seed: number;
  // Scenario-version ids that belong to this scenario, used to match the caller's owned
  // runs (GET /runs is already owner-scoped server-side) to a "Resume latest run" action.
  versionIds: string[];
}

const SCENARIO_LAUNCH_CONFIG: Record<string, ScenarioLaunchConfig> = {
  'scenario:operation-silent-relay': {
    packagePath: 'scenarios/operation-silent-relay',
    seed: 1000,
    versionIds: ['scenario-version:1.0.0-silent-relay'],
  },
};

function scenarioPackagePath(scenarioId: string): string {
  const configured = SCENARIO_LAUNCH_CONFIG[scenarioId];
  if (configured) {
    return configured.packagePath;
  }
  // Fallback for scenarios without explicit config: derive from the id slug.
  return `scenarios/${scenarioId.split(':')[1] ?? ''}`;
}

function scenarioSeed(scenarioId: string): number {
  return SCENARIO_LAUNCH_CONFIG[scenarioId]?.seed ?? 1000;
}

interface RunSummary {
  id: string;
  scenarioVersionId: string;
  status: string;
  startedAt: string;
  ownerUserId?: string | null;
}

function latestOwnedRun(
  scenarioId: string,
  runs: RunSummary[] | undefined,
): RunSummary | undefined {
  const versionIds = SCENARIO_LAUNCH_CONFIG[scenarioId]?.versionIds;
  if (!versionIds || !runs?.length) {
    return undefined;
  }
  const matching = runs.filter((run) => versionIds.includes(run.scenarioVersionId));
  if (!matching.length) {
    return undefined;
  }
  // Most recent by start time. GET /runs only returns the caller's own runs (admins see
  // all), so any match here is a run the current account may resume.
  return [...matching].sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
}

export default function ScenariosPage() {
  const router = useRouter();
  const scenariosQuery = useScenarios();
  const runsQuery = useRuns();
  const createRun = useCreateRun();

  const startRun = (scenarioId: string) => {
    void createRun
      .mutateAsync({
        scenarioPackagePath: scenarioPackagePath(scenarioId),
        seed: scenarioSeed(scenarioId),
      })
      .then((result) => {
        router.push(`/runs/${result.run.id}`);
      });
  };

  return (
    <CommandCentreShell>
      <Panel
        title="Scenario selection"
        description="Start a new run of a scenario, or resume a run this account already owns."
      >
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
                  render: (row: { id: string }) => {
                    const scenarioId = row.id;
                    const latestRun = latestOwnedRun(scenarioId, runsQuery.data as RunSummary[]);
                    const isDemoRun = latestRun?.ownerUserId === DEMO_OWNER_USER_ID;
                    return (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          size="sm"
                          data-testid={`start-run-${scenarioId}`}
                          disabled={createRun.isPending}
                          onClick={() => {
                            startRun(scenarioId);
                          }}
                        >
                          Start new run
                        </Button>
                        {latestRun ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            data-testid={`resume-run-${scenarioId}`}
                            onClick={() => {
                              router.push(`/runs/${latestRun.id}`);
                            }}
                          >
                            {isDemoRun ? 'Open demo run' : 'Resume latest run'} ({latestRun.status})
                          </Button>
                        ) : null}
                      </div>
                    );
                  },
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
