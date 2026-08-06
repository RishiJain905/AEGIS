/**
 * BUG-036: replay was dead for every real run — "0 of 0 · range 0–0", no graph — because
 * a graph node reconstructed from events carries `clusterId: null` and this package only
 * accepted `undefined`. One rejected field discards the whole payload, so a Python model
 * that declares `X | None` and a Zod schema that only tolerates `undefined` is not a
 * cosmetic divergence: it silently deletes a feature.
 *
 * The shared fixtures cannot catch this on their own — they carry populated values, so the
 * null branch of every nullable field goes untested. These cases pin the nulls that real
 * payloads actually carry.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  evidenceSchema,
  graphNodeSchema,
  providerCredentialStatusSchema,
  replayStateSchema,
  runLoadoutSchema,
  safeParseContract,
} from '../src/index';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const validDir = path.resolve(testDir, '../../../tests/contract/fixtures/valid');

function readFixture(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(path.join(validDir, `${name}.json`), 'utf-8')) as Record<
    string,
    unknown
  >;
}

describe('nullable parity with the Python contracts', () => {
  it('accepts a graph node with no cluster', () => {
    // aegis_contracts.graph.GraphNodeV1.cluster_id: ClusterId | None
    const node = { ...readFixture('graph_node_v1'), clusterId: null };
    expect(safeParseContract(graphNodeSchema, node).success).toBe(true);
  });

  it('accepts evidence with no asset', () => {
    // aegis_contracts.entities.EvidenceV1.asset_id: AssetId | None
    const evidence = { ...readFixture('evidence_v1'), assetId: null };
    expect(safeParseContract(evidenceSchema, evidence).success).toBe(true);
  });

  it('accepts a replay state whose nested nulls are all legal', () => {
    const state = readFixture('replay_state_v1') as {
      graph?: { nodes?: Record<string, unknown>[] } | null;
      evidence?: Record<string, unknown>[];
    };
    for (const node of state.graph?.nodes ?? []) {
      node.clusterId = null;
    }
    for (const evidence of state.evidence ?? []) {
      evidence.assetId = null;
    }
    expect(safeParseContract(replayStateSchema, state).success).toBe(true);
  });

  // A loadout can pin the run's model provider. Runs launched before those fields
  // existed carry neither, so all three shapes — absent, null, populated — have to
  // parse or the console drops every historical run's loadout.
  it('accepts a loadout however it expresses "no pinned provider"', () => {
    const stored = readFixture('run_loadout_v1');
    expect(safeParseContract(runLoadoutSchema, stored).success).toBe(true);
    expect(
      safeParseContract(runLoadoutSchema, { ...stored, providerId: null, modelId: null }).success,
    ).toBe(true);
  });

  it('accepts a loadout that pins a provider and model', () => {
    const pinned = {
      ...readFixture('run_loadout_v1'),
      providerId: 'openrouter',
      modelId: 'anthropic/claude-sonnet-4',
    };
    expect(safeParseContract(runLoadoutSchema, pinned).success).toBe(true);
  });

  it('rejects a loadout carrying anything key-shaped', () => {
    const smuggled = { ...readFixture('run_loadout_v1'), apiKey: 'sk-or-secret' };
    expect(safeParseContract(runLoadoutSchema, smuggled).success).toBe(false);
  });

  it('accepts an unconfigured credential status with no hint and no verification', () => {
    // aegis_contracts.provider_credentials.ProviderCredentialStatusV1
    const status = {
      schemaVersion: 1,
      provider: 'ollama-cloud',
      configured: false,
      keyHint: null,
      verifiedAt: null,
    };
    expect(safeParseContract(providerCredentialStatusSchema, status).success).toBe(true);
  });
});
