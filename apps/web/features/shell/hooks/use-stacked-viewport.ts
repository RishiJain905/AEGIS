'use client';

import { useEffect, useState } from 'react';

/**
 * True below the xl breakpoint, where the fixed-height cockpit gives way to the stacked
 * page flow. Expressed as a max-width query (not the inverse min-width) so environments
 * without real layout — jsdom's matchMedia stub answers `false` to everything — resolve
 * to the cockpit, which is the layout under test.
 */
export function useStackedViewport(): boolean {
  const [stacked, setStacked] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }
    const query = window.matchMedia('(max-width: 1279.98px)');
    const update = () => {
      setStacked(query.matches);
    };
    update();
    query.addEventListener('change', update);
    return () => {
      query.removeEventListener('change', update);
    };
  }, []);

  return stacked;
}
