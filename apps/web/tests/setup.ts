import 'vitest-axe/extend-expect';
import '@testing-library/jest-dom/vitest';

// jsdom does not define the WebGL interfaces. sigma's rendering bundle
// references `WebGLRenderingContext` at module scope (for GL enum constants),
// so importing the custom alive-edge programs under jsdom needs the globals to
// exist — no actual GL behavior is required (Sigma itself is mocked in tests).
const globalRef = globalThis as {
  WebGLRenderingContext?: unknown;
  WebGL2RenderingContext?: unknown;
};
if (typeof globalRef.WebGLRenderingContext === 'undefined') {
  globalRef.WebGLRenderingContext = function WebGLRenderingContext() {
    // jsdom stub — only referenced for GL enum constant lookups.
  };
}
if (typeof globalRef.WebGL2RenderingContext === 'undefined') {
  globalRef.WebGL2RenderingContext = function WebGL2RenderingContext() {
    // jsdom stub — only referenced for GL enum constant lookups.
  };
}

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
