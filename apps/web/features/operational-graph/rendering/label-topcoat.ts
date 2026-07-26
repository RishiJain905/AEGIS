import type Sigma from 'sigma';

import { computeLabelPillLayout, paintLabelPill, type LabelPillLayout } from './aegis-canvas-renderers';

interface LabelSourceData {
  label?: string;
  color: string;
  size: number;
  shape?: 'circle' | 'diamond' | 'square' | 'triangle' | 'hexagon';
  selected?: boolean;
  hovered?: boolean;
  riskBand?: string;
  incidentMarked?: boolean;
  evidenceMarked?: boolean;
}

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface LabelCandidate {
  id: string;
  priority: number;
  rect: Rect;
}

function rectsOverlap(a: Rect, b: Rect): boolean {
  return (
    a.left < b.left + b.width &&
    a.left + a.width > b.left &&
    a.top < b.top + b.height &&
    a.top + a.height > b.top
  );
}

/** Greedy highest-priority-first placement: a candidate is kept only if its
 * rect doesn't overlap any higher-(or-equal-)priority rect already kept.
 * Ties keep their input order (stable sort). Pure and Sigma-free so it's
 * cheap to unit test directly. */
export function selectNonCollidingLabels(candidates: LabelCandidate[]): Set<string> {
  const ordered = candidates
    .map((candidate, index) => ({ candidate, index }))
    .sort((a, b) => b.candidate.priority - a.candidate.priority || a.index - b.index);

  const kept: Rect[] = [];
  const result = new Set<string>();
  for (const { candidate } of ordered) {
    if (kept.some((rect) => rectsOverlap(rect, candidate.rect))) {
      continue;
    }
    kept.push(candidate.rect);
    result.add(candidate.id);
  }
  return result;
}

/** Higher wins the collision tie-break: an explicitly emphasized node's label
 * survives over a merely-larger one. Falls back to node size (a degree/
 * criticality proxy) so the ordering is still sensible with no emphasis. */
export function labelPriority(data: LabelSourceData): number {
  if (data.selected) return 100;
  if (data.hovered) return 90;
  if (data.incidentMarked) return 80;
  if (data.evidenceMarked) return 75;
  if (data.riskBand === 'critical') return 70;
  if (data.riskBand === 'high') return 60;
  // Capped comfortably below every emphasis tier above, so an unusually large
  // ordinary node can never outrank real emphasis on priority alone.
  return Math.min(data.size, 50);
}

/**
 * Repaints every currently-displayed node label pill on a canvas layer
 * positioned after Sigma's own topmost built-in layer ('hoverNodes'), with
 * two problems fixed in one pass that no single node's own draw call can see:
 *
 * 1. Z-order: Sigma tracks a `highlighted` node attribute for its own reasons
 *    (any such node gets its full WebGL body redrawn on 'hoverNodes' so it's
 *    never buried under labels — see Sigma's `renderHighlightedNodes`). This
 *    app also relies on that same attribute to drive status/evidence/
 *    incident badges in `drawAegisNodeHover`, so it stays true for nearly
 *    every node whenever labelMode is ALL. In a dense zone-sector layout our
 *    pill labels commonly reach a neighboring (likely also highlighted)
 *    node's position, so its disc/dot would land on the label text. This
 *    topcoat repaints labels above everything instead of narrowing
 *    `highlighted` (which would silently drop badges for most nodes).
 * 2. Label-vs-label collision and edge clipping: a single node's own draw
 *    call has no idea where its neighbors' pills land, or how wide the
 *    canvas is. This class collects every candidate's layout first, computed
 *    with `computeLabelPillLayout` (which already flips a pill to the node's
 *    left when the default right anchor would clip the canvas edge), then
 *    keeps the highest-priority non-overlapping subset via
 *    `selectNonCollidingLabels` — fewer, fully-legible labels rather than
 *    many partially painted over each other.
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
    const layouts = new Map<string, { layout: LabelPillLayout; data: LabelSourceData; y: number }>();
    const candidates: LabelCandidate[] = [];

    for (const nodeId of this.sigma.getNodeDisplayedLabels()) {
      const raw = this.sigma.getNodeDisplayData(nodeId);
      if (!raw || !raw.label) {
        continue;
      }
      const data = raw as unknown as LabelSourceData;
      // Match Sigma's own internal render transform exactly: nodeDataCache
      // entries (what getNodeDisplayData returns) are already in framed
      // graph space, so framedGraphToViewport is the right conversion here
      // - graphToViewport would re-normalize already-normalized coordinates.
      const { x, y } = this.sigma.framedGraphToViewport(raw);
      const size = this.sigma.scaleSize(raw.size);
      const layout = computeLabelPillLayout(context, { x, y, size, label: raw.label }, settings, width);
      if (!layout) {
        continue;
      }
      const positioned = { ...data, size };
      layouts.set(nodeId, { layout, data: positioned, y });
      candidates.push({
        id: nodeId,
        priority: labelPriority(positioned),
        rect: { left: layout.left, top: layout.top, width: layout.width, height: layout.height },
      });
    }

    const kept = selectNonCollidingLabels(candidates);
    for (const nodeId of kept) {
      const entry = layouts.get(nodeId);
      if (!entry) {
        continue;
      }
      paintLabelPill(context, entry.layout, { ...entry.data, y: entry.y });
    }
  }

  dispose(): void {
    this.sigma.off('afterRender', this.handleRender);
    this.sigma.off('resize', this.handleResize);
    // Canvas element removal is owned by sigma.kill().
  }
}
