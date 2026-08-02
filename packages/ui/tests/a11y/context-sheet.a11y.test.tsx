import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { ContextSheet } from '@aegis/ui';

afterEach(() => {
  cleanup();
});

describe('ContextSheet accessibility', () => {
  it('renders each side without axe violations', async () => {
    for (const side of ['left', 'right', 'bottom'] as const) {
      const { container, unmount } = render(
        <ContextSheet
          side={side}
          open
          onClose={vi.fn()}
          label="Inspector"
          subject="asset:web-01"
          data-testid="sheet"
        >
          <p>Sheet content</p>
          <button type="button">Act</button>
        </ContextSheet>,
      );
      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
      unmount();
    }
  });
});
