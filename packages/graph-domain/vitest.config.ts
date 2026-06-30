import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

const packageRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: [
      {
        find: '@aegis/graph-domain/fixtures/medium-graph-snapshot',
        replacement: path.join(packageRoot, 'src/fixtures/medium-graph-snapshot.ts'),
      },
      {
        find: '@aegis/graph-domain',
        replacement: path.join(packageRoot, 'src/index.ts'),
      },
      {
        find: '@aegis/contracts-ts',
        replacement: path.join(packageRoot, '../contracts-ts/src/index.ts'),
      },
    ],
  },
  test: {
    include: [
      '../../tests/unit/graph-domain/**/*.test.ts',
      '../../tests/performance/graph-domain/**/*.test.ts',
    ],
  },
});
