'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Button, EmptyState, ErrorState, LoadingState, cn, typographyTokens } from '@aegis/ui';

import type { RunLoadout } from '@/features/command-surface';
import {
  LoadoutLaunchDialog,
  SCENARIO_LAUNCH_CONFIG,
  TRAINING_SCENARIO_ID,
  launchSeedFor,
  scenarioPackagePathFor,
  scenarioSeedFor,
} from '@/features/loadout';
import { CommandCentreShell } from '@/features/shell/components/command-centre-shell';
import { resumeRun, useCreateRun } from '@/features/live-run';
import { ApiClientError } from '@/lib/api/types';
import { useRuns, useScenarios } from '@/features/shell/hooks/use-shell-queries';
import { useAuth } from '@/features/auth';
// Import the pure helpers directly (not the feature barrel) so the catalogue page does not
// pull the overlay/evidence/api graph into its bundle.
import { armTutorial } from '@/features/tutorial/tutorial-storage';

type ScenarioKind = 'tutorial' | 'live';

interface ScenarioPresentation {
  kind: ScenarioKind;
  badge: string;
  tagline: string;
  seedCaption: string;
  order: number;
}

// Catalogue framing: the training scenario is presented as the recommended first run
// (a guided tutorial), Silent Relay as the live, randomized operation. Copy keeps a
// confident ops-room register rather than gamer-cheese.
const SCENARIO_PRESENTATION: Record<string, ScenarioPresentation> = {
  [TRAINING_SCENARIO_ID]: {
    kind: 'tutorial',
    badge: 'Tutorial · Guided run',
    tagline:
      'Recommended first run. A hand-held walkthrough of a live blue-team engagement — read the floor, catch the first signal, task an AI copilot, and make the containment call, start to finish.',
    seedCaption: 'Deterministic training seed',
    order: 0,
  },
  'scenario:operation-silent-relay': {
    kind: 'live',
    badge: 'Live operation',
    tagline:
      'A randomized threat — no two runs alike. The server draws a fresh seed on every launch, so the hidden root cause changes each time. No walkthrough; you have the desk.',
    seedCaption: 'Randomized · server RNG',
    order: 1,
  },
};

function presentationFor(scenarioId: string): ScenarioPresentation {
  return (
    SCENARIO_PRESENTATION[scenarioId] ?? {
      kind: 'live',
      badge: 'Operation',
      tagline: 'A defensive scenario streaming synthetic telemetry into the command surface.',
      seedCaption: scenarioSeedFor(scenarioId) !== undefined ? 'Pinned seed' : 'Server RNG',
      order: 99,
    }
  );
}

interface RunSummary {
  id: string;
  scenarioVersionId: string;
  status: string;
  startedAt: string;
  createdAt?: string | null;
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
  // Most recent by wall-clock creation. `startedAt` is the deterministic scenario epoch —
  // identical for every run of the same scenario — so it cannot order runs; `createdAt`
  // (null on legacy rows) can. GET /runs only returns the caller's own runs (admins see
  // all), so any match here is a run the current account may resume.
  const sorted = [...matching].sort((a, b) => (a.createdAt ?? '').localeCompare(b.createdAt ?? ''));
  return sorted[sorted.length - 1];
}

// Quiet uppercase mono metadata chip — key/value pair, no chrome competing with the
// display name it sits beneath.
function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_70%,transparent)] px-2 py-1">
      <span className={cn(typographyTokens.monoSm, 'uppercase text-[var(--aegis-text-faint)]')}>
        {label}
      </span>
      <span className={cn(typographyTokens.monoSm, 'truncate text-[var(--aegis-text-secondary)]')}>
        {value}
      </span>
    </span>
  );
}

/**
 * What to tell the operator when a launch is refused.
 *
 * A pinned-seed scenario derives one run id for the whole database, so whoever launches it
 * first owns it. The server used to answer 200 with that run and the operator landed in a
 * workspace they had no permission to read; it now refuses with `RUN_OWNED_BY_ANOTHER_USER`,
 * and the refusal is only useful if we say what it was. (The tutorial no longer hits this —
 * it derives a per-operator seed — but the guard stays for any scenario that pins a shared
 * seed.)
 */
function launchErrorMessage(error: unknown): string {
  if (!(error instanceof ApiClientError)) {
    return 'Could not start the run. Check the connection and try again.';
  }
  if (error.code === 'RUN_OWNED_BY_ANOTHER_USER') {
    return `${error.message} Runs of this scenario are shared, so only its owner or an administrator can restart it.`;
  }
  if (error.status === 400) {
    return 'This scenario could not be launched — its package is unavailable on the server. Try Operation Silent Relay, or contact an operator to provision the scenario.';
  }
  return 'Could not start the run. Check the connection and try again.';
}

export default function ScenariosPage() {
  const router = useRouter();
  const { actor } = useAuth();
  const scenariosQuery = useScenarios();
  const runsQuery = useRuns();
  const createRun = useCreateRun();
  // Which live scenario is mid-launch in the loadout step, if any.
  const [loadoutScenarioId, setLoadoutScenarioId] = useState<string | null>(null);

  const launch = (scenarioId: string, loadout?: RunLoadout, commanderIntent?: string) => {
    const isTutorial = presentationFor(scenarioId).kind === 'tutorial';
    void createRun
      .mutateAsync({
        scenarioPackagePath: scenarioPackagePathFor(scenarioId),
        // undefined for seedless scenarios → server draws a random seed; the tutorial
        // derives a stable per-operator seed so each operator owns their own run.
        seed: launchSeedFor(scenarioId, actor?.userId ?? null),
        loadout,
        commanderIntent,
        // The tutorial's per-operator seed derives one run id per operator, so without this
        // a relaunch resumes the operator's own earlier training run — long since finished,
        // which drops them straight into the debrief. Ask the server to destroy and rebuild
        // it instead. Silent Relay is seedless and never reaches that server path.
        restartExisting: isTutorial,
      })
      .then((result) => {
        // Arm the guided walkthrough immediately so the coach mark is live the moment the
        // run page mounts, before the run detail round-trips.
        if (isTutorial) {
          armTutorial(result.run.id);
        }
        setLoadoutScenarioId(null);
        router.push(`/runs/${result.run.id}`);
      })
      .catch(() => {
        // A rejected launch (e.g. the server can't resolve the scenario package) must not
        // fail silently — close the loadout step and let the mutation's error surface below
        // instead of leaving the operator staring at an unresponsive button.
        setLoadoutScenarioId(null);
      });
  };

  const startRun = (scenarioId: string) => {
    // The tutorial launches straight into its deterministic guided walkthrough with default
    // capabilities; live operations get the pre-launch loadout step (the second variety axis).
    if (presentationFor(scenarioId).kind === 'tutorial') {
      launch(scenarioId);
      return;
    }
    setLoadoutScenarioId(scenarioId);
  };

  const loadoutScenarioName =
    scenariosQuery.data?.find((s: { id: string; name: string }) => s.id === loadoutScenarioId)
      ?.name ?? 'this operation';

  // Resume the caller's latest owned run. A paused run is resumed server-side before we
  // navigate, so the tick engine starts advancing it again the moment the operator opens it.
  const openLatestRun = (run: RunSummary) => {
    const navigate = () => {
      router.push(`/runs/${run.id}`);
    };
    if (run.status === 'paused') {
      void resumeRun(run.id)
        .then(navigate)
        .catch(() => {
          navigate();
        });
      return;
    }
    navigate();
  };

  const isLoading = scenariosQuery.isPending || runsQuery.isPending;
  const hasScenarios = scenariosQuery.isSuccess && scenariosQuery.data.length > 0;

  return (
    <CommandCentreShell>
      <section aria-labelledby="scenarios-heading" className="flex flex-col gap-8">
        <header className="flex flex-col gap-5 border-b border-[var(--aegis-border-subtle)] pb-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex max-w-2xl flex-col gap-3">
            <span className="inline-flex items-center gap-2">
              <span
                aria-hidden="true"
                className="size-1.5 rounded-full bg-[var(--aegis-accent-cyan)] shadow-[0_0_10px_var(--aegis-accent-cyan)]"
              />
              <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
                AEGIS Command · Mission control
              </span>
            </span>
            <h1
              id="scenarios-heading"
              className="font-[family-name:var(--aegis-font-display)] text-[2rem] font-semibold leading-[1.1] tracking-[-0.01em] text-[var(--aegis-text-primary)] sm:text-[2.5rem]"
            >
              Operations catalogue
            </h1>
            <p className="text-[0.9375rem] leading-6 text-[var(--aegis-text-secondary)]">
              Launch a new run of a defensive scenario, or resume a run this account already owns.
              Each operation streams synthetic telemetry into the live command surface.
            </p>
          </div>
          <div className="flex items-center gap-4">
            {hasScenarios ? (
              <div className="hidden flex-col items-end gap-1 sm:flex">
                <span className="font-[family-name:var(--aegis-font-display)] text-2xl font-semibold tabular-nums text-[var(--aegis-text-primary)]">
                  {scenariosQuery.data.length}
                </span>
                <span className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-faint)]')}>
                  {scenariosQuery.data.length === 1 ? 'Operation' : 'Operations'}
                </span>
              </div>
            ) : null}
            <Link
              href="/design-system"
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--aegis-border-default)] bg-[color-mix(in_srgb,var(--aegis-surface-raised)_80%,transparent)] px-3 py-1.5 text-[0.6875rem] font-semibold uppercase leading-none tracking-[0.08em] text-[var(--aegis-text-secondary)] backdrop-blur-sm transition-colors duration-[var(--aegis-motion-duration-fast)] hover:border-[var(--aegis-accent-line)] hover:text-[var(--aegis-accent-strong)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--aegis-focus-ring)] motion-reduce:transition-none"
            >
              Design system
            </Link>
          </div>
        </header>

        {isLoading ? <LoadingState message="Loading scenarios…" /> : null}

        {scenariosQuery.isError ? (
          <ErrorState
            data-testid="scenarios-error"
            message="Unable to load scenarios."
            onRetry={() => void scenariosQuery.refetch()}
          />
        ) : null}

        {createRun.isError ? (
          <ErrorState
            data-testid="create-run-error"
            message={launchErrorMessage(createRun.error)}
            onRetry={() => {
              createRun.reset();
            }}
          />
        ) : null}

        {scenariosQuery.isSuccess && scenariosQuery.data.length === 0 ? (
          <EmptyState
            data-testid="scenarios-empty"
            title="No scenarios available"
            description="Published scenarios will appear here when the simulation platform is connected."
          />
        ) : null}

        {hasScenarios ? (
          <ul
            data-testid="scenarios-table"
            aria-label="Available scenarios"
            className="flex flex-col gap-4"
          >
            {[...scenariosQuery.data]
              .sort(
                (a: { name: string; id: string }, b: { name: string; id: string }) =>
                  presentationFor(a.id).order - presentationFor(b.id).order ||
                  a.name.localeCompare(b.name),
              )
              .map((scenario: { name: string; id: string }) => {
                const scenarioId = scenario.id;
                const presentation = presentationFor(scenarioId);
                const isTutorial = presentation.kind === 'tutorial';
                const latestRun = latestOwnedRun(scenarioId, runsQuery.data as RunSummary[]);
                // The tutorial's run id is pinned by its seed, so launching it again does
                // not add a run — it replaces the one that exists. Say so on the button
                // rather than promising a "new run" that overwrites the operator's last one.
                const isRestart = isTutorial && latestRun !== undefined;
                return (
                  <li key={scenarioId}>
                    <article
                      data-testid={`scenario-card-${scenarioId}`}
                      className={cn(
                        'group relative flex flex-col gap-6 overflow-hidden rounded-[var(--aegis-radius-xl)] border bg-[color-mix(in_srgb,var(--aegis-surface-panel)_82%,transparent)] p-6 shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl transition-[border-color,box-shadow] duration-[var(--aegis-motion-duration-normal)] before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-[var(--aegis-border-highlight)] hover:shadow-[var(--aegis-shadow-panel-hover)] motion-reduce:transition-none sm:flex-row sm:items-center sm:justify-between sm:gap-8',
                        isTutorial
                          ? 'border-[color-mix(in_srgb,var(--aegis-accent-line)_50%,transparent)] hover:border-[color-mix(in_srgb,var(--aegis-accent-line)_70%,transparent)]'
                          : 'border-[var(--aegis-border-subtle)] hover:border-[color-mix(in_srgb,var(--aegis-accent-line)_55%,transparent)]',
                      )}
                    >
                      <div className="flex min-w-0 flex-col gap-3">
                        <span
                          className={cn(
                            'inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1',
                            typographyTokens.monoSm,
                            'uppercase',
                            isTutorial
                              ? 'border-[color-mix(in_srgb,var(--aegis-accent-line)_55%,transparent)] bg-[var(--aegis-accent-soft)] text-[var(--aegis-accent-strong)]'
                              : 'border-[var(--aegis-border-default)] bg-[color-mix(in_srgb,var(--aegis-surface-elevated)_70%,transparent)] text-[var(--aegis-text-secondary)]',
                          )}
                          data-testid={`scenario-badge-${scenarioId}`}
                        >
                          <span
                            aria-hidden="true"
                            className={cn(
                              'size-1.5 rounded-full',
                              isTutorial
                                ? 'bg-[var(--aegis-accent-cyan)] shadow-[0_0_8px_var(--aegis-accent-cyan)]'
                                : 'bg-[var(--aegis-text-faint)]',
                            )}
                          />
                          {presentation.badge}
                        </span>
                        <h2 className="font-[family-name:var(--aegis-font-display)] text-xl font-semibold tracking-[-0.005em] text-[var(--aegis-text-primary)] sm:text-2xl">
                          {scenario.name}
                        </h2>
                        <p className="max-w-xl text-[0.8125rem] leading-5 text-[var(--aegis-text-secondary)]">
                          {presentation.tagline}
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <MetaChip label="ID" value={scenarioId} />
                          <MetaChip
                            label="Seed"
                            value={`${launchSeedFor(scenarioId, actor?.userId ?? null)?.toString() ?? 'Server RNG'} · ${presentation.seedCaption}`}
                          />
                          {latestRun ? (
                            <span className="inline-flex items-center gap-1.5 rounded-[var(--aegis-radius-sm)] border border-[color-mix(in_srgb,var(--aegis-accent-line)_45%,transparent)] bg-[var(--aegis-accent-soft)] px-2 py-1">
                              <span
                                aria-hidden="true"
                                className="size-1.5 rounded-full bg-[var(--aegis-accent-cyan)]"
                              />
                              <span
                                className={cn(
                                  typographyTokens.monoSm,
                                  'uppercase text-[var(--aegis-accent-strong)]',
                                )}
                              >
                                Run available
                              </span>
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex flex-none flex-col gap-2 sm:items-end">
                        <div className="flex flex-wrap items-center gap-2.5">
                          <Button
                            data-testid={`start-run-${scenarioId}`}
                            disabled={createRun.isPending}
                            onClick={() => {
                              startRun(scenarioId);
                            }}
                          >
                            {isRestart ? 'Restart training run' : 'Start new run'}
                          </Button>
                          {latestRun ? (
                            <Button
                              variant="secondary"
                              data-testid={`resume-run-${scenarioId}`}
                              onClick={() => {
                                openLatestRun(latestRun);
                              }}
                            >
                              Resume latest run ({latestRun.status})
                            </Button>
                          ) : null}
                        </div>
                        {isRestart ? (
                          <p
                            data-testid={`restart-note-${scenarioId}`}
                            className="max-w-[19rem] text-[0.6875rem] leading-4 text-[var(--aegis-text-faint)] sm:text-right"
                          >
                            Replaces the existing training run and starts the walkthrough from the
                            top.
                          </p>
                        ) : null}
                      </div>
                    </article>
                  </li>
                );
              })}
          </ul>
        ) : null}
      </section>

      <LoadoutLaunchDialog
        open={loadoutScenarioId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setLoadoutScenarioId(null);
          }
        }}
        scenarioName={loadoutScenarioName}
        launching={createRun.isPending}
        onLaunch={(loadout, commanderIntent) => {
          if (loadoutScenarioId) {
            launch(loadoutScenarioId, loadout, commanderIntent);
          }
        }}
      />
    </CommandCentreShell>
  );
}
