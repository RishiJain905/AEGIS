import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { LoadoutLaunchDialog } from './loadout-launch-dialog';

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('LoadoutLaunchDialog', () => {
  it('launches with the default loadout (bias guard + threat tempo on, investigate)', async () => {
    const onLaunch = vi.fn();
    const user = userEvent.setup();
    render(
      <LoadoutLaunchDialog
        open
        onOpenChange={vi.fn()}
        scenarioName="Operation Silent Relay"
        launching={false}
        onLaunch={onLaunch}
      />,
    );
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(
      {
        schemaVersion: 1,
        biasGuard: true,
        threatTempo: true,
        roe: 'investigate',
      },
      undefined,
    );
  });

  it('reflects toggling a capability off and choosing a different RoE', async () => {
    const onLaunch = vi.fn();
    const user = userEvent.setup();
    render(
      <LoadoutLaunchDialog
        open
        onOpenChange={vi.fn()}
        scenarioName="Operation Silent Relay"
        launching={false}
        onLaunch={onLaunch}
      />,
    );
    await user.click(screen.getByLabelText(/Bias guard/i));
    await user.click(screen.getByTestId('roe-option-forward_deployed'));
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(
      {
        schemaVersion: 1,
        biasGuard: false,
        threatTempo: true,
        roe: 'forward_deployed',
      },
      undefined,
    );
  });

  it('passes a typed commander intent as the second onLaunch argument', async () => {
    const onLaunch = vi.fn();
    const user = userEvent.setup();
    render(
      <LoadoutLaunchDialog
        open
        onOpenChange={vi.fn()}
        scenarioName="Operation Silent Relay"
        launching={false}
        onLaunch={onLaunch}
      />,
    );
    const field = screen.getByTestId('loadout-commander-intent');
    expect(field).toHaveAttribute('maxLength', '280');
    await user.type(field, '  protect student records  ');
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(expect.any(Object), 'protect student records');
  });

  it('passes undefined intent when the field is left blank', async () => {
    const onLaunch = vi.fn();
    const user = userEvent.setup();
    render(
      <LoadoutLaunchDialog
        open
        onOpenChange={vi.fn()}
        scenarioName="Operation Silent Relay"
        launching={false}
        onLaunch={onLaunch}
      />,
    );
    await user.click(screen.getByTestId('loadout-launch-confirm'));
    expect(onLaunch).toHaveBeenCalledWith(expect.any(Object), undefined);
  });
});
