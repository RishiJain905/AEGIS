import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ContextSheet } from '@aegis/ui';

afterEach(() => {
  cleanup();
});

function renderSheet(onClose = vi.fn(), open = true) {
  render(
    <ContextSheet
      side="right"
      open={open}
      onClose={onClose}
      label="Inspector"
      subject="asset:web-01"
      data-testid="sheet"
    >
      <button type="button">First</button>
      <button type="button">Second</button>
    </ContextSheet>,
  );
  return onClose;
}

describe('ContextSheet', () => {
  it('renders nothing while closed', () => {
    renderSheet(vi.fn(), false);
    expect(screen.queryByTestId('sheet')).not.toBeInTheDocument();
  });

  it('is a labelled dialog that takes focus on open', () => {
    renderSheet();
    const sheet = screen.getByRole('dialog', { name: 'Inspector' });
    expect(sheet).toHaveFocus();
    expect(sheet).toHaveAttribute('data-side', 'right');
    expect(screen.getByText('asset:web-01')).toBeInTheDocument();
  });

  it('closes on Escape and on its close button', async () => {
    const user = userEvent.setup();
    const onClose = renderSheet();

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId('sheet-close'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('wraps Tab inside the sheet — dialog focus semantics', async () => {
    const user = userEvent.setup();
    renderSheet();

    // Panel -> close button -> First -> Second -> wraps back to the close button.
    await user.tab();
    expect(screen.getByTestId('sheet-close')).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Second' })).toHaveFocus();
    await user.tab();
    expect(screen.getByTestId('sheet-close')).toHaveFocus();

    await user.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Second' })).toHaveFocus();
  });

  it('returns focus to where the operator was when it closes', async () => {
    const user = userEvent.setup();
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button
            type="button"
            onClick={() => {
              setOpen(true);
            }}
          >
            Summon
          </button>
          <ContextSheet
            side="left"
            open={open}
            onClose={() => {
              setOpen(false);
            }}
            label="Copilot"
            data-testid="sheet"
          />
        </div>
      );
    }
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Summon' }));
    expect(screen.getByRole('dialog', { name: 'Copilot' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Summon' })).toHaveFocus();
  });
});
