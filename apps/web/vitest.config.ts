import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  esbuild: {
    jsx: 'automatic',
  },
  test: {
    environment: 'jsdom',
    include: [
      'tests/**/*.test.ts',
      'tests/**/*.test.tsx',
      'features/**/*.test.ts',
      'features/**/*.test.tsx',
      'lib/**/*.test.ts',
      'stores/**/*.test.ts',
      '../../tests/performance/graph/**/*.test.ts',
      '../../tests/performance/cinematic/**/*.test.ts',
      '../../tests/unit/graph-fixtures/**/*.test.ts',
      '../../tests/unit/replay-ui/**/*.test.ts',
      '../../tests/unit/cinematic/**/*.test.ts',
      'fixtures/**/*.test.ts',
    ],
    setupFiles: ['./tests/setup.ts'],
  },
  resolve: {
    alias: [
      {
        find: '@/features',
        replacement: path.resolve(__dirname, './features'),
      },
      { find: '@/workers', replacement: path.resolve(__dirname, './workers') },
      { find: '@/lib', replacement: path.resolve(__dirname, './lib') },
      { find: '@/stores', replacement: path.resolve(__dirname, './stores') },
      {
        find: '@/fixtures',
        replacement: path.resolve(__dirname, './fixtures'),
      },
      {
        find: '@/components',
        replacement: path.resolve(__dirname, './components'),
      },
      { find: '@', replacement: path.resolve(__dirname, './src') },
      {
        find: '@aegis/ui',
        replacement: path.resolve(__dirname, '../../packages/ui/src/index.ts'),
      },
      {
        find: '@aegis/contracts-ts',
        replacement: path.resolve(__dirname, '../../packages/contracts-ts/src/index.ts'),
      },
      {
        find: '@aegis/graph-domain',
        replacement: path.resolve(__dirname, '../../packages/graph-domain/src/index.ts'),
      },
    ],
  },
});
