'use client';

import { useEffect, useState } from 'react';

import type { ResolvedTheme, ThemePreference } from '@/features/shell/contracts/panel-preferences';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const PREFERS_LIGHT_QUERY = '(prefers-color-scheme: light)';

/**
 * Resolve a stored theme preference to the concrete theme to apply. `system`
 * follows the OS preference (defaulting to dark unless the OS explicitly asks
 * for light); `light`/`dark` are honoured verbatim.
 */
export function resolveTheme(theme: ThemePreference, prefersLight: boolean): ResolvedTheme {
  if (theme === 'system') {
    return prefersLight ? 'light' : 'dark';
  }
  return theme;
}

export interface UseThemeResult {
  /** The stored operator preference (`system` | `light` | `dark`). */
  theme: ThemePreference;
  /** The concrete theme in effect right now, after resolving `system`. */
  resolvedTheme: ResolvedTheme;
  /** Persist a new theme preference. */
  setTheme: (theme: ThemePreference) => void;
}

/**
 * Read and set the operator theme preference. Tracks the live OS
 * `prefers-color-scheme` so `resolvedTheme` stays correct in `system` mode.
 *
 * This hook does not touch the DOM — `ThemeManager` owns applying `data-theme`
 * so there is a single writer. Consume this hook wherever a control needs to
 * read or change the theme (e.g. the rail/design-system toggles).
 */
export function useTheme(): UseThemeResult {
  const theme = useWorkspaceUiStore((state) => state.panelPreferences.theme);
  const setTheme = useWorkspaceUiStore((state) => state.setTheme);

  const [prefersLight, setPrefersLight] = useState<boolean>(() =>
    typeof window === 'undefined' ? false : window.matchMedia(PREFERS_LIGHT_QUERY).matches,
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const media = window.matchMedia(PREFERS_LIGHT_QUERY);
    const onChange = (event: MediaQueryListEvent) => {
      setPrefersLight(event.matches);
    };
    setPrefersLight(media.matches);
    media.addEventListener('change', onChange);
    return () => {
      media.removeEventListener('change', onChange);
    };
  }, []);

  return { theme, resolvedTheme: resolveTheme(theme, prefersLight), setTheme };
}
