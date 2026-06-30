'use client';

import { useEffect, useState } from 'react';

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

export function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia(REDUCED_MOTION_QUERY);
    const update = (): void => {
      setReducedMotion(mediaQuery.matches);
    };

    update();
    mediaQuery.addEventListener('change', update);
    return () => {
      mediaQuery.removeEventListener('change', update);
    };
  }, []);

  return reducedMotion;
}

export function getReducedMotionPreference(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}
