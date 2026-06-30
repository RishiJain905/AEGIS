/**
 * @vitest-environment jsdom
 */
import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { getReducedMotionPreference, useReducedMotion } from '../src/motion/use-reduced-motion';

describe('reduced motion', () => {
  let matchMediaListeners: Array<(event: MediaQueryListEvent) => void>;
  let matches: boolean;

  beforeEach(() => {
    matchMediaListeners = [];
    matches = false;
    vi.stubGlobal('matchMedia', (query: string) => {
      const mediaQueryList = {
        get matches() {
          return matches;
        },
        media: query,
        addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) => {
          matchMediaListeners.push(listener);
        },
        removeEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) => {
          matchMediaListeners = matchMediaListeners.filter((l) => l !== listener);
        },
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        onchange: null,
      };
      return mediaQueryList;
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reads reduced motion preference', () => {
    matches = true;
    expect(getReducedMotionPreference()).toBe(true);
  });

  it('updates hook when preference changes', () => {
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);

    matches = true;
    act(() => {
      for (const listener of matchMediaListeners) {
        listener({ matches: true } as MediaQueryListEvent);
      }
    });

    expect(result.current).toBe(true);
  });
});
