import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';

import type { RunLoadout } from '@/features/command-surface/contracts';

import { LoadoutChips } from './loadout-chips';

const loadout: RunLoadout = {
  schemaVersion: 1,
  biasGuard: true,
  threatTempo: false,
  roe: 'investigate',
};

afterEach(() => {
  cleanup();
});

describe('LoadoutChips', () => {
  it('renders nothing when there is neither loadout nor intent', () => {
    const { container } = render(<LoadoutChips loadout={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the INTENT chip with the full intent as accessible name when set', () => {
    render(
      <LoadoutChips
        loadout={loadout}
        commanderIntent="protect student records; preserve evidence"
      />,
    );
    const chip = screen.getByTestId('loadout-intent-chip');
    expect(chip).toHaveAttribute('title', 'protect student records; preserve evidence');
    expect(chip).toHaveTextContent(
      "Commander's intent: protect student records; preserve evidence",
    );
  });

  it('does not render the INTENT chip when intent is null or blank', () => {
    render(<LoadoutChips loadout={loadout} commanderIntent="   " />);
    expect(screen.queryByTestId('loadout-intent-chip')).toBeNull();
  });

  it('renders the INTENT chip even when the run has no loadout', () => {
    render(<LoadoutChips loadout={null} commanderIntent="hold the logistics zone" />);
    expect(screen.getByTestId('loadout-intent-chip')).toBeInTheDocument();
  });

  it('names the pinned provider and model when the run was launched on a cloud provider', () => {
    render(
      <LoadoutChips
        loadout={{ ...loadout, providerId: 'openrouter', modelId: 'anthropic/claude-sonnet-4' }}
      />,
    );
    const chip = screen.getByTestId('loadout-model-chip');
    expect(chip).toHaveTextContent('OpenRouter');
    expect(chip).toHaveTextContent('anthropic/claude-sonnet-4');
  });

  it('omits the model chip for a run on the deployment default', () => {
    render(<LoadoutChips loadout={loadout} />);
    expect(screen.queryByTestId('loadout-model-chip')).toBeNull();
  });

  it('has no axe violations', async () => {
    const { container } = render(
      <LoadoutChips loadout={loadout} commanderIntent="protect student records" />,
    );
    // color-contrast is disabled: the chip palette is driven by CSS custom properties that
    // jsdom does not load, so axe cannot measure real contrast here (verified in Chrome).
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } });
    expect(results.violations).toHaveLength(0);
  });
});
