import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';

import {
  ComponentPlayground,
  PlatformReference,
  TokenInspector,
} from '@/components/design-system/operational-panels';
import { countTokens } from '@/components/design-system/token-catalogue';

describe('design-system operational panels', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders a copyable swatch for every catalogued token', () => {
    render(<TokenInspector />);
    const swatches = screen.getAllByTestId(/^token-swatch-/);
    expect(swatches.length).toBe(countTokens());
    const [firstSwatch] = swatches;
    if (!firstSwatch) {
      throw new Error('expected at least one token swatch');
    }
    fireEvent.click(firstSwatch);
    expect(within(firstSwatch).getByText('Copied')).toBeInTheDocument();
  });

  it('updates the playground preview and JSX snippet from live props', () => {
    render(<ComponentPlayground />);
    fireEvent.click(screen.getByTestId('playground-variant-outline'));
    fireEvent.click(screen.getByTestId('playground-size-lg'));
    const snippet = screen.getByText(/<Button variant="outline" size="lg">/);
    expect(snippet).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('playground-copy-snippet'));
    expect(screen.getByTestId('playground-copy-snippet').textContent).toBe('Copied');
  });

  it('lists keyboard shortcuts and semantic legends', () => {
    render(<PlatformReference />);
    const table = screen.getByTestId('keyboard-reference');
    expect(within(table).getByText('Play / pause playback')).toBeInTheDocument();
    expect(screen.getByText('Under investigation')).toBeInTheDocument();
    expect(screen.getByText('score ≥ 0.85')).toBeInTheDocument();
  });

  it('has no detectable accessibility violations', async () => {
    const { container } = render(
      <>
        <TokenInspector />
        <ComponentPlayground />
        <PlatformReference />
      </>,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
