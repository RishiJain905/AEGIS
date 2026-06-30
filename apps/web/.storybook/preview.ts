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
      values: [{ name: 'command-centre', value: '#0b0f14' }],
    },
  },
};

export default preview;
