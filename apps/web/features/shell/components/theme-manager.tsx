'use client';

import { useEffect, useState } from 'react';

import { useTheme } from '@/features/shell/hooks/use-theme';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

/**
 * Single authoritative writer of the `data-theme` attribute on the document
 * root. Mounted once near the app root; keeps the attribute in sync with the
 * resolved theme after hydration.
 *
 * The pre-paint value is set by `ThemeScript` directly from persisted storage,
 * so this must NOT write until the persisted store has finished rehydrating —
 * otherwise it would briefly clobber the correct value with the pre-hydration
 * default (`system`) and cause a flash. Once hydrated, the resolved theme
 * matches what `ThemeScript` already applied, so the first sync is a no-op and
 * only genuine preference/OS changes move the attribute afterwards.
 */
export function ThemeManager(): null {
  const { resolvedTheme } = useTheme();
  const [hydrated, setHydrated] = useState<boolean>(() =>
    useWorkspaceUiStore.persist.hasHydrated(),
  );

  useEffect(() => {
    const unsubscribe = useWorkspaceUiStore.persist.onFinishHydration(() => {
      setHydrated(true);
    });
    if (useWorkspaceUiStore.persist.hasHydrated()) {
      setHydrated(true);
    }
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    document.documentElement.setAttribute('data-theme', resolvedTheme);
  }, [hydrated, resolvedTheme]);

  return null;
}
