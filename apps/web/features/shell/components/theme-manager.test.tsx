import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/features/shell/hooks/use-theme', () => ({
  useTheme: () => ({ theme: 'dark', resolvedTheme: 'dark', setTheme: vi.fn() }),
}));

// Mirrors the real SSR condition: zustand's persist middleware resolves its
// default `localStorage`-backed storage at store-creation time, and on the
// server that throws and short-circuits before `.persist` is ever attached
// to the store object — so `useWorkspaceUiStore.persist` is `undefined`
// during every SSR render pass. `renderToString` (used here) is what
// reproduces this faithfully: like real SSR it runs only the render phase
// and never runs effects, so this exercises exactly the code path that must
// not touch `.persist` — unlike `@testing-library/react`'s `render`, which
// flushes effects synchronously and would fail for the unrelated reason that
// `.persist` never becomes available client-side either in this mock.
vi.mock('@/stores/workspace-ui-store', () => ({
  useWorkspaceUiStore: vi.fn(),
}));

import { ThemeManager } from '@/features/shell/components/theme-manager';

describe('ThemeManager', () => {
  it('does not throw when the persist API is unavailable (SSR)', () => {
    expect(() => renderToString(<ThemeManager />)).not.toThrow();
  });
});
