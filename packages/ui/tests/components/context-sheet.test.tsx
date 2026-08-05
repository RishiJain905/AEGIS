import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect, useRef, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ContextSheet, resetSheetFocusTracking } from '@aegis/ui';

afterEach(() => {
  cleanup();
  resetSheetFocusTracking();
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

  // Summoning a sheet can fold the surface its invoker lived on — an alert card's asset
  // button dies when the signals stack collapses for the sheet in the same commit. Focus
  // must not fall to <body>.
  it('falls back when the element that summoned it no longer exists', async () => {
    const user = userEvent.setup();
    const fallback = document.createElement('button');
    fallback.textContent = 'Signals';
    document.body.append(fallback);

    function Harness() {
      const [open, setOpen] = useState(false);
      const [showInvoker, setShowInvoker] = useState(true);
      return (
        <div>
          {showInvoker ? (
            <button
              type="button"
              onClick={() => {
                setOpen(true);
                setShowInvoker(false);
              }}
            >
              Summon
            </button>
          ) : null}
          <ContextSheet
            side="right"
            open={open}
            onClose={() => {
              setOpen(false);
            }}
            label="Inspector"
            restoreFocusTo={() => fallback}
            data-testid="sheet"
          />
        </div>
      );
    }
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Summon' }));
    expect(screen.getByRole('dialog', { name: 'Inspector' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(document.activeElement).not.toBe(document.body);
    expect(fallback).toHaveFocus();
    fallback.remove();
  });

  // Typing on the console opens the copilot sheet AND seeds its composer. The composer
  // claims focus from a child effect, which runs before the sheet's own; pulling focus back
  // to the panel here would drop every keystroke that followed the first.
  it('leaves focus where its content already put it', () => {
    function Composer() {
      const ref = useRef<HTMLTextAreaElement>(null);
      useEffect(() => {
        ref.current?.focus();
      }, []);
      return <textarea ref={ref} aria-label="Ask the copilot" />;
    }
    render(
      <ContextSheet side="left" open onClose={vi.fn()} label="Copilot" data-testid="sheet">
        <Composer />
      </ContextSheet>,
    );

    expect(screen.getByLabelText('Ask the copilot')).toHaveFocus();
  });

  it('reads a subject by name with its identity underneath', () => {
    render(
      <ContextSheet
        side="right"
        open
        onClose={vi.fn()}
        label="Inspector"
        subject="Analyst workstation"
        subjectDetail="asset:device-analyst-01"
        data-testid="sheet"
      />,
    );

    expect(screen.getByTestId('sheet-subject')).toHaveTextContent('Analyst workstation');
    expect(screen.getByTestId('sheet-subject-detail')).toHaveTextContent('asset:device-analyst-01');
  });
});
