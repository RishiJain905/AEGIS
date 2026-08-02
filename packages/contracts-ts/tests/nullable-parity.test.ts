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
  replayStateSchema,
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
});
