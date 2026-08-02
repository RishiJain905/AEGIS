import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useRef, useState } from 'react';
import { afterEach, describe, expect, it } from 'vitest';

import { useToolbarRovingFocus } from './use-toolbar-roving-focus';

function Harness({ extra = false }: { extra?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useToolbarRovingFocus(ref);
  return (
    <div role="toolbar" aria-label="Console" ref={ref}>
      <button type="button">One</button>
      <button type="button">Two</button>
      <button type="button">Three</button>
      {extra ? <button type="button">Four</button> : null}
    </div>
  );
}

afterEach(() => {
  cleanup();
});

describe('useToolbarRovingFocus', () => {
  it('makes the toolbar a single Tab stop', () => {
    render(<Harness />);
    expect(screen.getByRole('button', { name: 'One' })).toHaveAttribute('tabindex', '0');
    expect(screen.getByRole('button', { name: 'Two' })).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('button', { name: 'Three' })).toHaveAttribute('tabindex', '-1');
  });

  it('moves through controls with arrows, Home and End, wrapping at the edges', () => {
    render(<Harness />);
    const one = screen.getByRole('button', { name: 'One' });
    const two = screen.getByRole('button', { name: 'Two' });
    const three = screen.getByRole('button', { name: 'Three' });

    one.focus();
    fireEvent.keyDown(one, { key: 'ArrowRight' });
    expect(two).toHaveFocus();
    expect(two).toHaveAttribute('tabindex', '0');
    expect(one).toHaveAttribute('tabindex', '-1');

    fireEvent.keyDown(two, { key: 'End' });
    expect(three).toHaveFocus();

    fireEvent.keyDown(three, { key: 'ArrowRight' });
    expect(one).toHaveFocus();

    fireEvent.keyDown(one, { key: 'ArrowLeft' });
    expect(three).toHaveFocus();

    fireEvent.keyDown(three, { key: 'Home' });
    expect(one).toHaveFocus();
  });

  it('folds newly arrived controls into the roving order (tape beats land constantly)', async () => {
    function Growing() {
      const [extra, setExtra] = useState(false);
      return (
        <div>
          <button
            type="button"
            onClick={() => {
              setExtra(true);
            }}
          >
            grow
          </button>
          <Harness extra={extra} />
        </div>
      );
    }
    render(<Growing />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'grow' }));
      // MutationObserver callbacks run as microtasks.
      await Promise.resolve();
    });
    expect(screen.getByRole('button', { name: 'Four' })).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('button', { name: 'One' })).toHaveAttribute('tabindex', '0');
  });
});
