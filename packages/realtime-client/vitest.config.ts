import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

const packageRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: [
      {
        find: '@aegis/realtime-client',
        replacement: path.join(packageRoot, 'src/index.ts'),
      },
      {
        find: '@aegis/contracts-ts',
        replacement: path.join(packageRoot, '../contracts-ts/src/index.ts'),
      },
    ],
  },
  test: {
    include: ['tests/**/*.test.ts'],
  },
});
