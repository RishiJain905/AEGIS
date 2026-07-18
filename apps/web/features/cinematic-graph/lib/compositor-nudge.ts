/**
 * Chromium can leave stale GPU tiles composited over the page after a large
 * WebGL canvas is destroyed (observed as full-page tiling corruption when
 * switching 3D → 2D). Forcing a layer invalidation on the document root plus a
 * resize event makes the compositor redraw everything and lets the freshly
 * mounted Sigma canvases measure their container.
 */
export function nudgeCompositorAfterModeSwitch(): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return;
  }
  try {
    window.requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'));
      const root = document.documentElement;
      const previousTransform = root.style.transform;
      root.style.transform = 'translateZ(0)';
      window.requestAnimationFrame(() => {
        root.style.transform = previousTransform;
        window.dispatchEvent(new Event('resize'));
      });
    });
  } catch {
    // Best-effort repaint nudge; never let it break mode switching.
  }
}
