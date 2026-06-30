import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { GraphEdgeV1, GraphNodeV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import {
  GRAPH_EDGE_SCHEMA_VERSION,
  GRAPH_NODE_SCHEMA_VERSION,
  GRAPH_SNAPSHOT_SCHEMA_VERSION,
} from '@aegis/contracts-ts';

const __dirname = dirname(fileURLToPath(import.meta.url));
const NODE_COUNT = 2500;
const EDGES_PER_NODE = 2;

function padId(index: number): string {
  return String(index).padStart(5, '0');
}

function buildMediumSnapshot(): GraphSnapshotV1 {
  const nodes: GraphNodeV1[] = [];
  const edges: GraphEdgeV1[] = [];

  for (let i = 0; i < NODE_COUNT; i += 1) {
    const id = `asset:node-${padId(i)}`;
    nodes.push({
      schemaVersion: GRAPH_NODE_SCHEMA_VERSION,
      id,
      entityType: 'asset',
      assetType: i % 3 === 0 ? 'service' : i % 3 === 1 ? 'device' : 'database',
      label: `Node ${String(i)}`,
      clusterId: `business-unit:cluster-${String(i % 20).padStart(2, '0')}`,
      riskScore: (i % 100) / 100,
      criticality: ((i + 7) % 100) / 100,
      status: i % 17 === 0 ? 'suspicious' : 'normal',
      revision: 1,
    });
  }

  for (let i = 0; i < NODE_COUNT; i += 1) {
    for (let j = 1; j <= EDGES_PER_NODE; j += 1) {
      const targetIndex = (i + j * 37) % NODE_COUNT;
      if (targetIndex === i) {
        continue;
      }
      const edgeId = `edge:medium-${padId(i)}-${padId(targetIndex)}-${String(j)}`;
      edges.push({
        schemaVersion: GRAPH_EDGE_SCHEMA_VERSION,
        id: edgeId,
        source: `asset:node-${padId(i)}`,
        target: `asset:node-${padId(targetIndex)}`,
        relationshipType: j % 2 === 0 ? 'COMMUNICATED_WITH' : 'DEPENDS_ON',
        directed: true,
        confidence: 0.9,
        riskContribution: 0.1,
        firstSeenAt: '2026-01-01T00:00:00.000Z',
        lastSeenAt: '2026-06-30T00:00:00.000Z',
        eventCount: i % 5 === 0 ? 10 : 0,
        revision: 1,
      });
    }
  }

  return {
    schemaVersion: GRAPH_SNAPSHOT_SCHEMA_VERSION,
    runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    sequence: 1000,
    capturedAt: '2026-06-30T03:00:00.000Z',
    nodes,
    edges,
    clusters: [],
    revision: 1,
  };
}

const snapshot = buildMediumSnapshot();
const outputPath = join(__dirname, '../fixtures/medium-graph-snapshot.json');
writeFileSync(outputPath, `${JSON.stringify(snapshot, null, 2)}\n`);
console.log(
  `Wrote medium snapshot with ${String(snapshot.nodes.length)} nodes and ${String(snapshot.edges.length)} edges to ${outputPath}`,
);
