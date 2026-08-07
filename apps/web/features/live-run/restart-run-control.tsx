'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@aegis/ui';

import { readRunLoadout } from '@/features/command-surface';
import {
  isTutorialScenario,
  scenarioIdForRunVersion,
  scenarioPackagePathFor,
} from '@/features/loadout';
import { useRun } from '@/features/shell/hooks/use-shell-queries';
import { armTutorial } from '@/features/tutorial/tutorial-storage';
import { isRunTerminal } from '@/lib/run-status';

import { useLiveRun } from './live-run-provider';
import { useCreateRun } from './use-run-commands';

/**
 * The way back from a dead end: relaunch the finished run's own scenario, seed, loadout and
 * commander's intent from the cockpit (P1, owner-reported 2026-08-07).
 *
 * A run's id derives from (seed, scenario_version_id), so relaunching the same seed resolves
 * to the same run id — the server's `restartExisting` path destroys the finished run and
 * rebuilds it from scratch under that id. That is why this is a confirmed, destructive
 * action: the run's timeline, after-action report and replay are discarded with it. The
 * confirm dialog says exactly that, and the relaunch carries the run's own loadout so the
 * operator gets the engagement they chose back, not a default one.
 *
 * Rendered only when the run is terminal and its scenario is launchable; an unknown
 * scenario version has no relaunch path, and the catalogue remains the way to a fresh
 * start.
 */
export function RestartRunControl({ runId }: { runId: string }) {
  const liveRun = useLiveRun();
  const router = useRouter();
  const runQuery = useRun(runId);
  const createRun = useCreateRun();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const run = runQuery.data;
  const scenarioId = run ? scenarioIdForRunVersion(run.scenarioVersionId) : null;
  const terminal = isRunTerminal(liveRun?.state.runStatus);
  if (!terminal || run === undefined || scenarioId === null) {
    return null;
  }

  const restart = () => {
    setErrorMessage(null);
    void createRun
      .mutateAsync({
        scenarioPackagePath: scenarioPackagePathFor(scenarioId),
        // The run's own seed: the same hidden root cause, the same engagement, from the top.
        seed: run.seed,
        // The run's own loadout (RoE, capabilities, pinned provider/model). Absent on a
        // legacy run → omitted, so the server persists the default loadout.
        loadout: readRunLoadout(run) ?? undefined,
        commanderIntent: run.commanderIntent ?? undefined,
        // Same seed ⇒ same derived run id; the server destroys the finished run and
        // rebuilds it, which is what makes this a restart rather than a resume.
        restartExisting: true,
      })
      .then((result) => {
        // The tutorial's run id is unchanged by a restart, so the overlay would otherwise
        // keep showing the pre-restart cursor; re-arm it the same way a catalogue launch
        // does. Live operations have no overlay to re-arm.
        if (isTutorialScenario(scenarioId)) {
          armTutorial(result.run.id);
        }
        setConfirmOpen(false);
        // The run id is the same one the operator is already on, so the route alone would
        // not remount the cockpit — the epoch query param keys the shell, forcing a fresh
        // bootstrap of the rebuilt run.
        router.push(`/runs/${result.run.id}?restart=${String(Date.now())}`);
      })
      .catch((error: unknown) => {
        // Keep the dialog open so the operator sees why and can retry.
        setErrorMessage(error instanceof Error ? error.message : 'The run could not be restarted.');
      });
  };

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        className="text-xs"
        data-testid="live-restart"
        title="Relaunch this scenario with the same seed and loadout."
        onClick={() => {
          setErrorMessage(null);
          setConfirmOpen(true);
        }}
      >
        Restart
      </Button>
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent data-testid="restart-run-dialog">
          <DialogHeader>
            <DialogTitle>Restart this run?</DialogTitle>
            <DialogDescription>
              This replaces the current run — its timeline, after-action report and replay are
              discarded — and starts a fresh engagement with the same seed and loadout.
              {isTutorialScenario(scenarioId)
                ? ' The guided walkthrough restarts from the top.'
                : ''}
            </DialogDescription>
          </DialogHeader>

          <p className="px-6 font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
            Seed {run.seed} · same hidden root cause
          </p>

          {errorMessage ? (
            <p
              role="alert"
              data-testid="restart-run-error"
              className="px-6 text-xs leading-5 text-[var(--aegis-risk-high)]"
            >
              {errorMessage}
            </p>
          ) : null}

          <DialogFooter>
            <Button
              variant="ghost"
              disabled={createRun.isPending}
              onClick={() => {
                setConfirmOpen(false);
              }}
            >
              Cancel
            </Button>
            <Button
              data-testid="restart-run-confirm"
              disabled={createRun.isPending}
              onClick={restart}
            >
              {createRun.isPending ? 'Restarting…' : 'Restart run'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
