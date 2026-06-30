import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    setupFiles: ['./tests/setup.ts'],
  },
  resolve: {
    alias: {
      '@aegis/ui': path.resolve(__dirname, './src/index.ts'),
      '@aegis/contracts-ts': path.resolve(__dirname, '../contracts-ts/src/index.ts'),
    },
  },
});
