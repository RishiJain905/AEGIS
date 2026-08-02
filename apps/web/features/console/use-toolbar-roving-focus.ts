'use client';

import { useEffect, type RefObject } from 'react';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]',
].join(', ');

/**
 * Roving tabindex for a toolbar: the whole container is one Tab stop, and Arrow keys
 * (plus Home/End) move through its controls. Built for the cockpit console, whose
 * children change constantly — every new tape beat is a button — so membership is
 * re-derived on DOM mutation rather than registered.
 */
export function useToolbarRovingFocus(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const root = ref.current;
    if (!root) {
      return;
    }

    const items = () =>
      Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
        (element) =>
          element.closest('[hidden]') === null && element.getAttribute('aria-hidden') !== 'true',
      );

    let active: HTMLElement | null = null;

    const apply = () => {
      const list = items();
      const first = list[0];
      if (first === undefined) {
        return;
      }
      if (active === null || !root.contains(active) || active.hasAttribute('disabled')) {
        active = first;
      }
      for (const element of list) {
        element.tabIndex = element === active ? 0 : -1;
      }
    };

    const onFocusIn = (event: FocusEvent) => {
      const target = event.target;
      if (target instanceof HTMLElement && target !== root && active !== target) {
        active = target;
        apply();
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
        return;
      }
      const list = items();
      const current = document.activeElement;
      const index = current instanceof HTMLElement ? list.indexOf(current) : -1;
      if (index === -1) {
        return;
      }
      event.preventDefault();
      const next =
        event.key === 'ArrowLeft'
          ? list[(index - 1 + list.length) % list.length]
          : event.key === 'ArrowRight'
            ? list[(index + 1) % list.length]
            : event.key === 'Home'
              ? list[0]
              : list[list.length - 1];
      if (next !== undefined) {
        active = next;
        apply();
        next.focus();
      }
    };

    apply();
    // New tape beats and enable/disable flips re-derive membership. Our own tabIndex
    // writes mutate the `tabindex` attribute, which is deliberately NOT in the filter —
    // observing it would loop.
    const observer = new MutationObserver(apply);
    observer.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled'],
    });
    root.addEventListener('focusin', onFocusIn);
    root.addEventListener('keydown', onKeyDown);
    return () => {
      observer.disconnect();
      root.removeEventListener('focusin', onFocusIn);
      root.removeEventListener('keydown', onKeyDown);
    };
  }, [ref]);
}
