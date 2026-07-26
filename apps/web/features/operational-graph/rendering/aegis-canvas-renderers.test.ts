import { describe, expect, it } from 'vitest';

import { computeLabelPillLayout } from './aegis-canvas-renderers';

/** Minimal CanvasRenderingContext2D stub: 8px per character, no font metrics
 * beyond that, so pill widths are hand-computable in the assertions below. */
function fakeContext(): CanvasRenderingContext2D {
  return {
    save: () => undefined,
    restore: () => undefined,
    measureText: (text: string) => ({ width: text.length * 8 }) as TextMetrics,
    set font(_value: string) {
      // no-op
    },
  } as unknown as CanvasRenderingContext2D;
}

const settings = { labelSize: 12, labelWeight: '600', labelFont: 'monospace' };

describe('computeLabelPillLayout', () => {
  it('returns null for an unlabeled node', () => {
    const context = fakeContext();
    expect(computeLabelPillLayout(context, { x: 0, y: 0, size: 10 }, settings, 2000)).toBeNull();
  });

  it('anchors to the right of the node when there is room', () => {
    const context = fakeContext();
    const layout = computeLabelPillLayout(
      context,
      { x: 100, y: 50, size: 10, label: 'foo' },
      settings,
      2000,
    );
    expect(layout).not.toBeNull();
    // right anchor: left = x + size + 8 = 118; width = textWidth(24) + 23 + 15 = 62
    expect(layout).toMatchObject({ text: 'foo', left: 118, width: 62, markerX: 129, textX: 141 });
    expect(layout?.left).toBeLessThan((layout?.left ?? 0) + (layout?.width ?? 0));
  });

  it('flips to the node\'s left when the right anchor would clip the canvas edge', () => {
    const context = fakeContext();
    // right anchor would be left=1968, width=62 -> right edge 2030 > canvasWidth 2000.
    const layout = computeLabelPillLayout(
      context,
      { x: 1950, y: 50, size: 10, label: 'foo' },
      settings,
      2000,
    );
    expect(layout).not.toBeNull();
    // left anchor: right = x - size - 8 = 1932; left = right - width(62) = 1870
    expect(layout).toMatchObject({ left: 1870, width: 62, markerX: 1921, textX: 1885 });
    // Fully on-screen, unlike the naive right anchor would have been.
    expect((layout?.left ?? 0) + (layout?.width ?? 0)).toBeLessThanOrEqual(2000);
  });

  it('clamps on-screen when neither side fits cleanly', () => {
    const context = fakeContext();
    // canvasWidth 50 is narrower than the pill (62) either side of x=5.
    const layout = computeLabelPillLayout(
      context,
      { x: 5, y: 50, size: 10, label: 'foo' },
      settings,
      50,
    );
    expect(layout).not.toBeNull();
    expect(layout?.left).toBeGreaterThanOrEqual(0);
    expect((layout?.left ?? 0) + (layout?.width ?? 0)).toBeGreaterThanOrEqual(0);
  });

  it('truncates a pathologically long label with an ellipsis, well past ordinary asset names', () => {
    const context = fakeContext();
    const longLabel = 'x'.repeat(100); // 800px at 8px/char, far past the 260px cap
    const layout = computeLabelPillLayout(
      context,
      { x: 100, y: 50, size: 10, label: longLabel },
      settings,
      2000,
    );
    expect(layout?.text.endsWith('…')).toBe(true);
    expect(layout?.text.length).toBeLessThan(longLabel.length);
  });
});
