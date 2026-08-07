/**
 * The one place that knows how a scenario id launches: which package path to hand the
 * server, whether the seed is pinned or per-operator, and which scenario-version ids belong
 * to it.
 *
 * The catalogue page uses it to launch and to match owned runs to a "Resume latest run"
 * action; the cockpit's restart control uses the same table in reverse — a run carries its
 * `scenarioVersionId`, and this module is what turns that back into a launchable package
 * path. Two surfaces, one answer to "what is this scenario and how does it start".
 */

import { deriveTrainingSeed } from '@/features/tutorial/tutorial-seed';

export interface ScenarioLaunchConfig {
  packagePath: string;
  // A pinned seed makes the scenario deterministic on launch. Omit it (as Operation
  // Silent Relay does) to launch seedless, so the server draws a fresh random seed per
  // run — each run gets a different hidden root cause. Kept optional (not removed) so a
  // deterministic tutorial scenario can still pin a seed.
  seed?: number;
  // The tutorial derives a stable per-operator seed from the signed-in operator's user id
  // (see `deriveTrainingSeed`), so every operator owns their own training run instead of
  // the whole database sharing one run id — the cross-operator ownership dead end QA found
  // on 2026-08-06. The story is unaffected: the training scenario's attack branch is fixed,
  // so any seed produces the same scheduled attack events.
  perOperatorSeed?: boolean;
  // Scenario-version ids that belong to this scenario, used to match the caller's owned
  // runs (GET /runs is already owner-scoped server-side) to a "Resume latest run" action,
  // and by the cockpit's restart control to resolve a run back to its launchable scenario.
  versionIds: string[];
  // The guided walkthrough scenario. Restarting it re-arms the tutorial overlay; live
  // operations have no overlay to re-arm.
  tutorial?: boolean;
}

export const TRAINING_SCENARIO_ID = 'scenario:synthetic-training';

export const SCENARIO_LAUNCH_CONFIG: Record<string, ScenarioLaunchConfig> = {
  // The guided tutorial derives a per-operator seed so every training run tells the same
  // story — the walkthrough milestones line up deterministically — while each operator's
  // run stays their own.
  [TRAINING_SCENARIO_ID]: {
    packagePath: 'scenarios/synthetic-training',
    perOperatorSeed: true,
    tutorial: true,
    versionIds: ['scenario-version:1.0.0-synthetic-training'],
  },
  // The live operation launches seedless: the server draws a fresh random seed per run,
  // so the hidden root cause differs every time.
  'scenario:operation-silent-relay': {
    packagePath: 'scenarios/operation-silent-relay',
    versionIds: ['scenario-version:1.0.0-silent-relay'],
  },
};

export function scenarioPackagePathFor(scenarioId: string): string {
  const configured = SCENARIO_LAUNCH_CONFIG[scenarioId];
  if (configured) {
    return configured.packagePath;
  }
  // Fallback for scenarios without explicit config: derive from the id slug.
  return `scenarios/${scenarioId.split(':')[1] ?? ''}`;
}

export function scenarioSeedFor(scenarioId: string): number | undefined {
  return SCENARIO_LAUNCH_CONFIG[scenarioId]?.seed;
}

/**
 * The seed a launch of `scenarioId` will actually use, for the signed-in operator.
 *
 * Per-operator scenarios (the tutorial) derive their seed from the operator's user id, so
 * the catalogue can show the real number the run page will display. A null actor falls back
 * to the legacy shared seed — unreachable inside the auth gate, but harmless to guard.
 */
export function launchSeedFor(
  scenarioId: string,
  actorUserId: string | null,
): number | undefined {
  const config = SCENARIO_LAUNCH_CONFIG[scenarioId];
  if (config?.perOperatorSeed) {
    return deriveTrainingSeed(actorUserId);
  }
  return config?.seed;
}

/**
 * Resolve a run's `scenarioVersionId` back to the scenario that launched it, or `null` for
 * a version this deployment does not know how to launch. The cockpit's restart control
 * needs the scenario to relaunch the run; an unknown version means there is no launchable
 * path, and the catalogue remains the way back to a fresh start.
 */
export function scenarioIdForRunVersion(scenarioVersionId: string): string | null {
  for (const [scenarioId, config] of Object.entries(SCENARIO_LAUNCH_CONFIG)) {
    if (config.versionIds.includes(scenarioVersionId)) {
      return scenarioId;
    }
  }
  return null;
}

export function isTutorialScenario(scenarioId: string): boolean {
  return SCENARIO_LAUNCH_CONFIG[scenarioId]?.tutorial === true;
}
