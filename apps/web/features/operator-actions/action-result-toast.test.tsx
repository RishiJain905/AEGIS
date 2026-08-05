import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ActionResultSlot } from './action-result-slot';
import { ActionResultToast, type ActionResult } from './action-result-toast';

const EXECUTED: ActionResult = {
  commandLabel: 'Isolate host',
  assetLabel: 'Analyst workstation',
  response: {
    status: 'accepted',
    executed: true,
    reasonCodes: [],
  } as unknown as ActionResult['response'],
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** The console band, standing in for the real one: the result rail plus the controls. */
function ConsoleHarness({ children }: { children?: React.ReactNode }) {
  return (
    <div data-testid="cockpit-console">
      <ActionResultSlot />
      <div role="toolbar" aria-label="Console">
        <button type="button">Isolate</button>
        <button type="button">All actions</button>
      </div>
      {children}
    </div>
  );
}

describe('ActionResultToast', () => {
  it('renders into the console result rail, above the band and outside its hit area', () => {
    render(
      <ConsoleHarness>
        <ActionResultToast result={EXECUTED} onDismiss={vi.fn()} />
      </ConsoleHarness>,
    );

    const toast = screen.getByTestId('action-result-toast');
    const slot = screen.getByTestId('action-result-slot');
    const band = screen.getByRole('toolbar', { name: 'Console' });

    expect(slot).toContainElement(toast);
    // The result is laid out above the band, never over it — the whole point of the rail.
    expect(band).not.toContainElement(toast);
    expect(toast).not.toContainElement(band);
    expect(toast.compareDocumentPosition(band) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Nothing that could float over the console: no fixed placement, no stacking climb.
    expect(toast.className).not.toMatch(/\bfixed\b/);
    expect(toast.className).not.toMatch(/\bz-\d+\b/);
  });

  it('leaves on its own', () => {
    const onDismiss = vi.fn();
    render(
      <ConsoleHarness>
        <ActionResultToast result={EXECUTED} onDismiss={onDismiss} />
      </ConsoleHarness>,
    );

    expect(onDismiss).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(8_000);
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  // The owning surface re-renders constantly during a live run, and every render handed the
  // toast a new `onDismiss`. Keying the dismissal timer on that identity restarted it several
  // times a second, so the notification sat there — over the console — indefinitely.
  it('still leaves when its owner re-renders under it', () => {
    const onDismiss = vi.fn();
    function Owner() {
      return (
        <ConsoleHarness>
          <ActionResultToast
            result={EXECUTED}
            onDismiss={() => {
              onDismiss();
            }}
          />
        </ConsoleHarness>
      );
    }
    const { rerender } = render(<Owner />);

    for (let tick = 0; tick < 20; tick += 1) {
      act(() => {
        vi.advanceTimersByTime(400);
      });
      rerender(<Owner />);
    }

    expect(onDismiss).toHaveBeenCalled();
  });

  it('dismisses by hand', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const onDismiss = vi.fn();
    render(
      <ConsoleHarness>
        <ActionResultToast result={EXECUTED} onDismiss={onDismiss} />
      </ConsoleHarness>,
    );

    await user.click(screen.getByRole('button', { name: 'Dismiss notification' }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('says what policy did rather than claiming success', () => {
    render(
      <ConsoleHarness>
        <ActionResultToast
          result={{
            commandLabel: 'Disable account',
            assetLabel: 'j.okafor',
            response: {
              status: 'blocked',
              executed: false,
              reasonCodes: ['ROE_FORBIDS_ACCOUNT_DISABLE'],
            } as unknown as ActionResult['response'],
          }}
          onDismiss={vi.fn()}
        />
      </ConsoleHarness>,
    );

    const toast = screen.getByTestId('action-result-toast');
    expect(toast).toHaveAttribute('data-tone', 'block');
    expect(toast).toHaveTextContent('Blocked by policy');
    expect(toast).toHaveTextContent('ROE_FORBIDS_ACCOUNT_DISABLE');
  });
});
