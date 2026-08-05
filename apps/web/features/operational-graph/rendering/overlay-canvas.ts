import type Sigma from 'sigma';

/**
 * Logical size and device pixel ratio an overlay canvas must match to stay
 * registered with the nodes Sigma paints on its own layers.
 */
export interface OverlayCanvasMetrics {
  width: number;
  height: number;
  pixelRatio: number;
}

/**
 * Size an AEGIS overlay canvas (zone hulls, status signals, label topcoat) so
 * its drawing space lines up with Sigma's viewport coordinates.
 *
 * Both halves matter. The `width`/`height` *attributes* are the backing store
 * (logical size × dpr) and the `style` width/height are the CSS box. Sigma
 * only assigns the CSS box to layers registered with it, and only from inside
 * `resize()`, which returns early when the container size is unchanged. Layers
 * created by `sigma.createCanvas()` after the constructor's own `resize()` —
 * every overlay here — therefore keep a default CSS box unless the container
 * happens to change size later. A canvas with no CSS size renders at its
 * backing size, so with the dpr transform applied the overlay ends up drawn at
 * `dpr ×` the correct coordinates: hulls, labels, and halos slide away from
 * their nodes, the error growing with distance from the origin. Owning both
 * sides here makes the overlays independent of Sigma's resize bookkeeping.
 *
 * Returns whether anything changed, so callers can skip a redundant redraw.
 */
export function syncOverlayCanvas(
  canvas: HTMLCanvasElement,
  metrics: OverlayCanvasMetrics,
): boolean {
  const backingWidth = Math.round(metrics.width * metrics.pixelRatio);
  const backingHeight = Math.round(metrics.height * metrics.pixelRatio);
  const cssWidth = `${String(metrics.width)}px`;
  const cssHeight = `${String(metrics.height)}px`;

  if (
    canvas.width === backingWidth &&
    canvas.height === backingHeight &&
    canvas.style.width === cssWidth &&
    canvas.style.height === cssHeight
  ) {
    return false;
  }

  // Assigning width/height resets the 2D context (transform included), so the
  // dpr transform is re-applied after every resize.
  canvas.width = backingWidth;
  canvas.height = backingHeight;
  canvas.style.width = cssWidth;
  canvas.style.height = cssHeight;
  canvas.getContext('2d')?.setTransform(metrics.pixelRatio, 0, 0, metrics.pixelRatio, 0, 0);
  return true;
}

/** Current renderer metrics. Read live rather than cached: browser zoom and a
 * move between displays change the device pixel ratio without changing the
 * container's CSS size, which Sigma's own `resize()` treats as a no-op. */
export function overlayCanvasMetrics(sigma: Sigma): OverlayCanvasMetrics {
  const { width, height } = sigma.getDimensions();
  return { width, height, pixelRatio: window.devicePixelRatio || 1 };
}
