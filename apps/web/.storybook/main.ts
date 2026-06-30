import type { StorybookConfig } from '@storybook/react-vite';
import { mergeConfig } from 'vite';
import path from 'node:path';

const config: StorybookConfig = {
  stories: ['../components/design-system/**/*.stories.@(ts|tsx)'],
  addons: ['@storybook/addon-essentials', '@storybook/addon-a11y'],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  async viteFinal(config) {
    const tailwindcss = (await import('@tailwindcss/postcss')).default;
    return mergeConfig(config, {
      css: {
        postcss: {
          plugins: [tailwindcss()],
        },
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '../src'),
          '@aegis/ui/styles': path.resolve(__dirname, '../../../packages/ui/src/styles'),
          '@aegis/ui': path.resolve(__dirname, '../../../packages/ui/src/index.ts'),
        },
      },
    });
  },
};

export default config;
