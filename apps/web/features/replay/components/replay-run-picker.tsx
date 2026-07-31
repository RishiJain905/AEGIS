'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';

import type { RunV1 } from '@aegis/contracts-ts';
import { Badge, Button, EmptyState, ErrorState, LoadingState } from '@aegis/ui';

import { useRuns } from '@/features/shell/hooks/use-shell-queries';
import { queryKeys, useApiClient } from '@/lib/api';

/**
 * Maps a run's `scenarioVersionId` to the scenario it belongs to.
 *
 * A run only carries its scenario *version*, so the catalogue has to be walked to name it.
 * One query rather than one per scenario: the catalogue is two entries and the whole index
 * is useless until every version has been read.
 */
function useScenarioNameByVersionId() {
  const client = useApiClient();
  return useQuery({
    queryKey: [...queryKeys.scenarios.all, 'version-index'] as const,
    queryFn: async ({ signal }) => {
      const scenarios = await client.listScenarios(signal);
      const versionLists = await Promise.all(
        scenarios.map((scenario) => client.listScenarioVersions(scenario.id, signal)),
      );
      const index = new Map<string, string>();
      scenarios.forEach((scenario, position) => {
        for (const version of versionLists[position] ?? []) {
          index.set(version.id, scenario.name);
        }
      });
      return index;
    },
  });
}

const ACTIVE_STATUSES = new Set(['created', 'running', 'paused']);

/** Active runs first, newest first within each group (createdAt is the wall clock;
 * pre-migration rows carry none and sort last within their group). */
function orderedForReplay(runs: readonly RunV1[]): RunV1[] {
  return [...runs].sort((left, right) => {
    const leftActive = ACTIVE_STATUSES.has(left.status) ? 0 : 1;
    const rightActive = ACTIVE_STATUSES.has(right.status) ? 0 : 1;
    if (leftActive !== rightActive) {
      return leftActive - rightActive;
    }
    return (right.createdAt ?? '').localeCompare(left.createdAt ?? '');
  });
}

/** `2026-07-31T19:42:03Z` → `Jul 31, 19:42` — when the operator actually launched it. */
function launchedAt(createdAt: string | null | undefined): string | null {
  if (!createdAt) {
    return null;
  }
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** `2026-01-01T00:06:24Z` → `00:06:24`: how far into the operation the run reached. */
function simClock(simTime: string): string {
  return simTime.slice(11, 19) || simTime;
}

function RunRow({ run, scenarioName }: { run: RunV1; scenarioName: string | undefined }) {
  return (
    <li
      className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-[var(--aegis-border-subtle)] px-4 py-4 last:border-b-0 hover:bg-[var(--aegis-surface-raised)]"
      data-testid="replay-run-option"
      data-run-id={run.id}
    >
      <div className="min-w-56 flex-1">
        <p className="font-[family-name:var(--aegis-font-display)] text-sm font-semibold text-[var(--aegis-text-primary)]">
          {scenarioName ?? run.scenarioVersionId}
        </p>
        <p className="mt-1 truncate font-mono text-[0.6875rem] text-[var(--aegis-text-muted)]">
          {run.id}
        </p>
      </div>

      <Badge variant="outline" data-testid="replay-run-status">
        {run.status}
      </Badge>

      <dl className="flex gap-6 text-xs text-[var(--aegis-text-secondary)]">
        <div>
          <dt className="uppercase tracking-[0.12em] text-[0.625rem] text-[var(--aegis-text-muted)]">
            Seed
          </dt>
          <dd className="mt-0.5 font-mono">{run.seed}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-[0.12em] text-[0.625rem] text-[var(--aegis-text-muted)]">
            Sim clock
          </dt>
          <dd className="mt-0.5 font-mono">{simClock(run.simTime)}</dd>
        </div>
        {launchedAt(run.createdAt) ? (
          <div>
            <dt className="uppercase tracking-[0.12em] text-[0.625rem] text-[var(--aegis-text-muted)]">
              Launched
            </dt>
            <dd className="mt-0.5 font-mono" data-testid="replay-run-launched">
              {launchedAt(run.createdAt)}
            </dd>
          </div>
        ) : null}
      </dl>

      <Button asChild size="sm" variant="secondary">
        <Link href={`/replay/${run.id}`} data-testid="replay-run-open">
          Open replay
        </Link>
      </Button>
    </li>
  );
}

/**
 * Run-selection state for `/replay`.
 *
 * Replay used to be reachable only by typing a run's URL: the operations rail sent the
 * item to `/scenarios` whenever the current route had no run in it, so from the catalogue
 * the Replay link appeared to do nothing at all.
 */
export function ReplayRunPicker() {
  const runsQuery = useRuns();
  const scenarioNames = useScenarioNameByVersionId();

  if (runsQuery.isPending) {
    return <LoadingState message="Loading saved runs…" />;
  }

  if (runsQuery.isError) {
    return (
      <ErrorState
        data-testid="replay-runs-error"
        title="Unable to load saved runs"
        message="The run history could not be read. Retry, or open a run from the catalogue."
        onRetry={() => void runsQuery.refetch()}
      />
    );
  }

  const runs = orderedForReplay(runsQuery.data);

  if (runs.length === 0) {
    return (
      <EmptyState
        data-testid="replay-runs-empty"
        title="No saved runs to replay"
        description="Replay reconstructs a run from its recorded events. Launch an operation from the catalogue and it will appear here — during the run and after it ends."
      />
    );
  }

  return (
    <section aria-labelledby="replay-run-picker-heading" data-testid="replay-run-picker">
      <div className="mb-4">
        <h1
          id="replay-run-picker-heading"
          className="font-[family-name:var(--aegis-font-display)] text-lg font-semibold tracking-[0.02em] text-[var(--aegis-text-primary)]"
        >
          Replay a saved run
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-[var(--aegis-text-secondary)]">
          Every run keeps its full event history. Open one to scrub its timeline, inspect the graph
          as it stood at any sequence, and compare states — all read-only.
        </p>
      </div>

      <ul className="overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-panel)]">
        {runs.map((run) => (
          <RunRow
            key={run.id}
            run={run}
            scenarioName={scenarioNames.data?.get(run.scenarioVersionId)}
          />
        ))}
      </ul>
    </section>
  );
}
