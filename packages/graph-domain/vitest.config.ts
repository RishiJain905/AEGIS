import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

const packageRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      '@aegis/graph-domain': path.join(packageRoot, 'src/index.ts'),
      '@aegis/contracts-ts': path.join(packageRoot, '../contracts-ts/src/index.ts'),
    },
  },
  test: {
    include: [
      '../../tests/unit/graph-domain/**/*.test.ts',
      '../../tests/performance/graph-domain/**/*.test.ts',
    ],
  },
});
