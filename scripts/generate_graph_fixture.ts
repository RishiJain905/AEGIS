import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  buildStressGraphSnapshot,
  buildTargetGraphSnapshot,
} from '../packages/graph-domain/src/fixtures/graph-performance-snapshots';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const outputDir = resolve(root, 'apps/web/fixtures/generated');

function writeFixture(name: string, snapshot: ReturnType<typeof buildTargetGraphSnapshot>): void {
  const path = resolve(outputDir, `${name}.json`);
  writeFileSync(path, `${JSON.stringify(snapshot, null, 2)}\n`, 'utf8');
  console.log(
    `wrote ${path} (${String(snapshot.nodes.length)} nodes, ${String(snapshot.edges.length)} edges)`,
  );
}

mkdirSync(outputDir, { recursive: true });
writeFixture('graph-target', buildTargetGraphSnapshot());
writeFixture('graph-stress', buildStressGraphSnapshot());
