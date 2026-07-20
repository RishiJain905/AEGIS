import type { Preview } from '@storybook/react';

import './storybook.css';

const preview: Preview = {
  parameters: {
    controls: { expanded: true },
    a11y: {
      test: 'todo',
    },
    backgrounds: {
      default: 'command-centre',
      values: [
        { name: 'command-centre', value: '#0a0a0e' },
        { name: 'command-centre-light', value: '#f4f2ec' },
      ],
    },
  },
  // Theme is a global toolbar control so the a11y addon (and manual review) can
  // exercise every story in both the dark default and the light Foundry/Maven
  // theme (§8: a11y checks re-run against both themes, not just dark).
  globalTypes: {
    theme: {
      description: 'Command-centre theme',
      defaultValue: 'dark',
      toolbar: {
        title: 'Theme',
        icon: 'mirror',
        items: [
          { value: 'dark', title: 'Dark' },
          { value: 'light', title: 'Light' },
        ],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    (Story, context) => {
      const theme = (context.globals.theme as string | undefined) ?? 'dark';
      if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-theme', theme);
      }
      return Story();
    },
  ],
};

export default preview;
