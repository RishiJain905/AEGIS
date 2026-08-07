import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { deriveTrainingSeed } from '@/features/tutorial/tutorial-seed';

import {
  SCENARIO_LAUNCH_CONFIG,
  TRAINING_SCENARIO_ID,
  isTutorialScenario,
  launchSeedFor,
  scenarioIdForRunVersion,
  scenarioPackagePathFor,
  scenarioSeedFor,
} from './scenario-launch-config';

const SILENT_RELAY = 'scenario:operation-silent-relay';

/**
 * The scenario-version id a live Silent Relay run actually carries, observed on
 * `GET /api/v1/runs` against the running API on 2026-08-07 — every one of the nine runs in
 * that response, including run_HAQWCJAZ9P7CVFZVKMNEH9WXQ5, reported
 * `"scenarioVersionId": "scenario-version:1.0.0"`. The config previously listed only a
 * `-silent-relay` suffixed id that no run has ever carried, so the reverse lookup returned
 * null and the cockpit's restart control silently unmounted on every real run.
 */
const OBSERVED_SILENT_RELAY_VERSION_ID = 'scenario-version:1.0.0';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');

/**
 * The `metadata.version` the server turns into a run's `scenarioVersionId`
 * (`f"scenario-version:{manifest.metadata.version}"`). Read from the real package rather
 * than restated here, so a version bump in the scenario is what fails this test.
 */
function manifestVersion(packagePath: string): string {
  const manifest = readFileSync(resolve(REPO_ROOT, packagePath, 'manifest.yaml'), 'utf8');
  // The `metadata:` block only: its own two-space-indented lines (plus the deeper-indented
  // continuations of folded strings), up to the next top-level key.
  const metadata = /^metadata:\r?\n((?: {2}.*\r?\n|\r?\n)*)/m.exec(manifest)?.[1] ?? '';
  const version = / {2}version:\s*(\S+)/.exec(metadata)?.[1];
  if (version === undefined) {
    throw new Error(`No metadata.version in ${packagePath}/manifest.yaml`);
  }
  return version;
}

describe('scenarioPackagePathFor', () => {
  it('returns the configured package path for a known scenario', () => {
    expect(scenarioPackagePathFor(TRAINING_SCENARIO_ID)).toBe('scenarios/synthetic-training');
    expect(scenarioPackagePathFor(SILENT_RELAY)).toBe('scenarios/operation-silent-relay');
  });

  it('derives a package path from the id slug for an unconfigured scenario', () => {
    expect(scenarioPackagePathFor('scenario:some-other-op')).toBe('scenarios/some-other-op');
  });

  it('never returns the empty slug fallback for a malformed id', () => {
    // The fallback is a last resort, not a crash: an id without a slug still yields a
    // path the server can answer "unknown scenario" for, rather than an empty string.
    expect(scenarioPackagePathFor('scenario:')).toBe('scenarios/');
  });
});

describe('scenarioSeedFor', () => {
  it('returns the pinned seed for a deterministic scenario', () => {
    expect(scenarioSeedFor(TRAINING_SCENARIO_ID)).toBeUndefined();
  });

  it('returns undefined for a seedless scenario (server RNG)', () => {
    expect(scenarioSeedFor(SILENT_RELAY)).toBeUndefined();
  });

  it('returns undefined for an unknown scenario', () => {
    expect(scenarioSeedFor('scenario:unknown')).toBeUndefined();
  });
});

describe('launchSeedFor', () => {
  it('derives a stable per-operator seed for the tutorial', () => {
    const seed = launchSeedFor(TRAINING_SCENARIO_ID, 'user:alice');
    expect(seed).toBe(deriveTrainingSeed('user:alice'));
    // Stable across calls — the same operator always relaunches the same run id.
    expect(launchSeedFor(TRAINING_SCENARIO_ID, 'user:alice')).toBe(seed);
  });

  it('gives each operator their own tutorial seed', () => {
    expect(launchSeedFor(TRAINING_SCENARIO_ID, 'user:alice')).not.toBe(
      launchSeedFor(TRAINING_SCENARIO_ID, 'user:bob'),
    );
  });

  it('falls back to the legacy shared seed when no actor is present', () => {
    expect(launchSeedFor(TRAINING_SCENARIO_ID, null)).toBe(1000);
  });

  it('returns no seed for a seedless scenario regardless of actor', () => {
    expect(launchSeedFor(SILENT_RELAY, 'user:alice')).toBeUndefined();
    expect(launchSeedFor(SILENT_RELAY, null)).toBeUndefined();
  });
});

describe('scenarioIdForRunVersion', () => {
  it('resolves the version id a real Silent Relay run carries', () => {
    // The case the restart control lives or dies on — see the provenance note above.
    expect(scenarioIdForRunVersion(OBSERVED_SILENT_RELAY_VERSION_ID)).toBe(SILENT_RELAY);
    expect(scenarioPackagePathFor(SILENT_RELAY)).toBe('scenarios/operation-silent-relay');
  });

  it('resolves a known scenario-version id back to its scenario', () => {
    expect(scenarioIdForRunVersion('scenario-version:1.0.0-synthetic-training')).toBe(
      TRAINING_SCENARIO_ID,
    );
    // Kept mapped for runs restored from a deployment that minted the suffixed id.
    expect(scenarioIdForRunVersion('scenario-version:1.0.0-silent-relay')).toBe(SILENT_RELAY);
  });

  it('returns null for a version this deployment cannot launch', () => {
    expect(scenarioIdForRunVersion('scenario-version:9.9.9-some-future-op')).toBeNull();
  });
});

describe('isTutorialScenario', () => {
  it('flags only the guided walkthrough scenario', () => {
    expect(isTutorialScenario(TRAINING_SCENARIO_ID)).toBe(true);
    expect(isTutorialScenario(SILENT_RELAY)).toBe(false);
    expect(isTutorialScenario('scenario:unknown')).toBe(false);
  });
});

describe('SCENARIO_LAUNCH_CONFIG', () => {
  it('keeps every configured scenario launchable and resolvable', () => {
    for (const [scenarioId, config] of Object.entries(SCENARIO_LAUNCH_CONFIG)) {
      expect(scenarioPackagePathFor(scenarioId)).toBe(config.packagePath);
      expect(config.versionIds.length).toBeGreaterThan(0);
      for (const versionId of config.versionIds) {
        expect(scenarioIdForRunVersion(versionId)).toBe(scenarioId);
      }
    }
  });

  it('lists the version id each scenario package will actually mint', () => {
    // The drift guard. A run's `scenarioVersionId` is minted server-side as
    // `scenario-version:{manifest.metadata.version}`, so bumping a scenario's manifest
    // version without adding the new id here breaks the lookup — and the failure mode is
    // silent (the restart control returns null, the catalogue stops matching owned runs),
    // which is exactly how the shipped config went a full release listing an id no run
    // ever carried. Reading the manifests makes that bump fail here first.
    for (const [scenarioId, config] of Object.entries(SCENARIO_LAUNCH_CONFIG)) {
      const mintedId = `scenario-version:${manifestVersion(config.packagePath)}`;
      expect(config.versionIds).toContain(mintedId);
      expect(scenarioIdForRunVersion(mintedId)).toBe(scenarioId);
    }
  });

  it('reads the real manifest versions the two shipped scenarios pin today', () => {
    // Pins the observed reality the guard above compares against, so a manifest edit that
    // happens to satisfy the guard still shows up as a deliberate change here. Silent
    // Relay's bare `1.0.0` is the whole reason this is a table and not a parse: the id
    // carries no scenario identity.
    expect(manifestVersion('scenarios/operation-silent-relay')).toBe('1.0.0');
    expect(manifestVersion('scenarios/synthetic-training')).toBe('1.0.0-synthetic-training');
  });
});
