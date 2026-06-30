import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  buildMediumGraphSnapshot,
  MEDIUM_GRAPH_EDGES_PER_NODE,
  MEDIUM_GRAPH_NODE_COUNT,
} from '../src/fixtures/medium-graph-snapshot';

const packageRoot = dirname(fileURLToPath(import.meta.url));
const outputPath = join(packageRoot, '../fixtures/medium-graph-snapshot.json');

const snapshot = buildMediumGraphSnapshot();
mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(snapshot, null, 2)}\n`);
console.log(
  `Wrote medium snapshot with ${String(snapshot.nodes.length)} nodes (${String(MEDIUM_GRAPH_NODE_COUNT)} expected) and ${String(snapshot.edges.length)} edges (${String(MEDIUM_GRAPH_EDGES_PER_NODE)} per node target) to ${outputPath}`,
);
