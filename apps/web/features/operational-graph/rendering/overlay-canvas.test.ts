import type Sigma from 'sigma';
import type Graph from 'graphology';
import { describe, expect, it, vi } from 'vitest';

import { syncOverlayCanvas } from './overlay-canvas';
import { ZoneOverlay } from './zone-overlay';
import { SignalOverlay } from './signal-overlay';
import { LabelTopcoat } from './label-topcoat';

/** Sigma double that reports a fixed viewport and, like the real renderer,
 * never emits 'resize' after the overlay layers are created. */
function fakeSigma(width: number, height: number) {
  const canvases: HTMLCanvasElement[] = [];
  return {
    canvases,
    sigma: {
      getDimensions: () => ({ width, height }),
      createCanvas: () => {
        const canvas = document.createElement('canvas');
        // jsdom ships no canvas backend; the overlays only ever use the
        // context optionally, and this test is about element geometry.
        canvas.getContext = () => null;
        canvases.push(canvas);
        return canvas;
      },
      on: vi.fn(),
      off: vi.fn(),
      getSettings: () => ({}),
      getNodeDisplayedLabels: () => [],
      graphToViewport: ({ x, y }: { x: number; y: number }) => ({ x, y }),
      framedGraphToViewport: ({ x, y }: { x: number; y: number }) => ({ x, y }),
      scaleSize: (size: number) => size,
    } as unknown as Sigma,
  };
}

const emptyGraph = { hasNode: () => false } as unknown as Graph;

describe('syncOverlayCanvas', () => {
  it('sets the backing store and the CSS box so drawing lands in viewport coordinates', () => {
    const canvas = document.createElement('canvas');
    expect(syncOverlayCanvas(canvas, { width: 1835, height: 586, pixelRatio: 0.9 })).toBe(true);

    expect(canvas.width).toBe(Math.round(1835 * 0.9));
    expect(canvas.height).toBe(Math.round(586 * 0.9));
    // Without the CSS box the canvas renders at its backing size, which scales
    // every drawn point by the pixel ratio about the top-left corner.
    expect(canvas.style.width).toBe('1835px');
    expect(canvas.style.height).toBe('586px');
  });

  it('is a no-op when nothing changed, and re-syncs when the pixel ratio does', () => {
    const canvas = document.createElement('canvas');
    syncOverlayCanvas(canvas, { width: 800, height: 600, pixelRatio: 1 });

    expect(syncOverlayCanvas(canvas, { width: 800, height: 600, pixelRatio: 1 })).toBe(false);

    expect(syncOverlayCanvas(canvas, { width: 800, height: 600, pixelRatio: 2 })).toBe(true);
    expect(canvas.width).toBe(1600);
    expect(canvas.style.width).toBe('800px');
  });
});

describe('overlay layers sized without a Sigma resize event', () => {
  // Regression: switching 2D -> 3D -> 2D remounts Sigma into a container that
  // is already at its final size, so Sigma's resize() early-returns and never
  // assigns a CSS box to layers created by createCanvas(). The overlays then
  // drew hulls, halos, and labels at pixelRatio x their true position, sliding
  // them off their nodes by more the further from the origin they sat.
  it.each([
    ['zone hulls', (sigma: Sigma) => new ZoneOverlay(sigma, emptyGraph)],
    ['status signals', (sigma: Sigma) => new SignalOverlay(sigma, emptyGraph, false)],
    ['label topcoat', (sigma: Sigma) => new LabelTopcoat(sigma)],
  ])('%s canvas matches the renderer viewport', (_name, create) => {
    const { sigma, canvases } = fakeSigma(1835, 586);
    vi.spyOn(window, 'devicePixelRatio', 'get').mockReturnValue(0.9);

    create(sigma);

    const canvas = canvases[0];
    expect(canvas).toBeDefined();
    expect(canvas?.style.width).toBe('1835px');
    expect(canvas?.style.height).toBe('586px');
    expect(canvas?.width).toBe(Math.round(1835 * 0.9));

    vi.restoreAllMocks();
  });
});
