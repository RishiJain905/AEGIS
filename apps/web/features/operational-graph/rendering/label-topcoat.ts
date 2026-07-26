import type Sigma from 'sigma';

import { drawAegisNodeLabel } from './aegis-canvas-renderers';

/**
 * Repaints every currently-displayed node label pill on a canvas layer
 * positioned after Sigma's own topmost built-in layer ('hoverNodes').
 *
 * Sigma tracks a `highlighted` node attribute for its own reasons: any node
 * with `highlighted: true` gets its full WebGL body redrawn on the
 * 'hoverNodes' canvas so a hovered/selected node is never visually buried
 * under overlapping labels (see Sigma's `renderHighlightedNodes`, the
 * "Draw WebGL nodes on top of the labels" step). This app also relies on
 * that same `highlighted` attribute to drive the status/evidence/incident
 * badge overlays in `drawAegisNodeHover`, so it stays true for nearly every
 * node whenever labelMode is ALL (the default for small scenarios) - not
 * just the literal hovered/selected node.
 *
 * The combination is what produced the "discs eating characters mid-word"
 * bug in dense zone sectors: because our pill labels commonly extend far
 * enough to reach a neighboring node's actual position, and that neighbor
 * is very likely itself `highlighted`, Sigma's own hoverNodes redraw (and
 * the small badge dots drawn in `drawAegisNodeHover`, both on layers above
 * Sigma's 'labels' canvas) can land on top of the label text.
 *
 * Rather than narrow the `highlighted` attribute (which would silently
 * drop status/evidence/incident badges for most nodes - a much worse
 * regression) or hand-roll spatial collision avoidance between labels and
 * neighboring nodes, this repaints the exact same label pills Sigma just
 * rendered on its own 'labels' canvas, on a layer that always wins: labels
 * end up above every node body and badge, guaranteed, regardless of which
 * nodes Sigma decided to redraw on top of what.
 */
export class LabelTopcoat {
  private readonly sigma: Sigma;
  private readonly canvas: HTMLCanvasElement;
  private readonly handleRender = () => {
    this.draw();
  };
  private readonly handleResize = () => {
    this.resizeCanvas();
    this.draw();
  };

  constructor(sigma: Sigma) {
    this.sigma = sigma;
    this.canvas = sigma.createCanvas('aegis-label-topcoat', { afterLayer: 'hoverNodes' });
    this.canvas.setAttribute('aria-hidden', 'true');
    this.canvas.style.pointerEvents = 'none';
    this.resizeCanvas();
    sigma.on('afterRender', this.handleRender);
    sigma.on('resize', this.handleResize);
  }

  private resizeCanvas(): void {
    const { width, height } = this.sigma.getDimensions();
    const ratio = window.devicePixelRatio || 1;
    this.canvas.width = width * ratio;
    this.canvas.height = height * ratio;
    const context = this.canvas.getContext('2d');
    context?.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  draw(): void {
    const context = this.canvas.getContext('2d');
    if (!context) {
      return;
    }
    const { width, height } = this.sigma.getDimensions();
    context.clearRect(0, 0, width, height);

    const settings = this.sigma.getSettings();
    for (const nodeId of this.sigma.getNodeDisplayedLabels()) {
      const data = this.sigma.getNodeDisplayData(nodeId);
      if (!data || !data.label) {
        continue;
      }
      // Match Sigma's own internal render transform exactly: nodeDataCache
      // entries (what getNodeDisplayData returns) are already in framed
      // graph space, so framedGraphToViewport is the right conversion here
      // - graphToViewport would re-normalize already-normalized coordinates.
      const { x, y } = this.sigma.framedGraphToViewport(data);
      const size = this.sigma.scaleSize(data.size);
      drawAegisNodeLabel(context, { ...data, x, y, size }, settings);
    }
  }

  dispose(): void {
    this.sigma.off('afterRender', this.handleRender);
    this.sigma.off('resize', this.handleResize);
    // Canvas element removal is owned by sigma.kill().
  }
}
