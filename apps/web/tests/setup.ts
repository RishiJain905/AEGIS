import 'vitest-axe/extend-expect';
import '@testing-library/jest-dom/vitest';

// jsdom does not implement `matchMedia`; provide the canonical stub so
// components that read `prefers-color-scheme` / `prefers-reduced-motion`
// (e.g. the shell theme hook) render in tests. Defaults to "no preference".
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
