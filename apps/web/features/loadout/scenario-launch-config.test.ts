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
  it('resolves a known scenario-version id back to its scenario', () => {
    expect(scenarioIdForRunVersion('scenario-version:1.0.0-synthetic-training')).toBe(
      TRAINING_SCENARIO_ID,
    );
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
});
