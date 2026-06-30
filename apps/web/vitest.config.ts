import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: [
      'tests/**/*.test.ts',
      'tests/**/*.test.tsx',
      'features/**/*.test.ts',
      'features/**/*.test.tsx',
      'lib/**/*.test.ts',
      'stores/**/*.test.ts',
    ],
    setupFiles: ['./tests/setup.ts'],
  },
  resolve: {
    alias: [
      { find: '@/features', replacement: path.resolve(__dirname, './features') },
      { find: '@/lib', replacement: path.resolve(__dirname, './lib') },
      { find: '@/stores', replacement: path.resolve(__dirname, './stores') },
      { find: '@/fixtures', replacement: path.resolve(__dirname, './fixtures') },
      { find: '@/components', replacement: path.resolve(__dirname, './components') },
      { find: '@', replacement: path.resolve(__dirname, './src') },
      { find: '@aegis/ui', replacement: path.resolve(__dirname, '../../packages/ui/src/index.ts') },
      {
        find: '@aegis/contracts-ts',
        replacement: path.resolve(__dirname, '../../packages/contracts-ts/src/index.ts'),
      },
    ],
  },
});
