import type Graph from 'graphology';
import type Sigma from 'sigma';

/** Worst security signal currently inside a zone, in escalation order. */
export type ZoneThreatLevel = 'none' | 'contained' | 'watch' | 'hostile';

export interface ZoneRenderState {
  id: string;
  label: string;
  memberIds: string[];
  threat: ZoneThreatLevel;
}

/** Roll member statuses up to the zone frame: any compromised member makes the
 * whole sector hostile; suspicious/under-investigation put it on watch. */
export function rollupZoneThreat(statuses: Iterable<string>): ZoneThreatLevel {
  let level: ZoneThreatLevel = 'none';
  for (const status of statuses) {
    if (status === 'compromised') {
      return 'hostile';
    }
    if (status === 'suspicious' || status === 'under_investigation') {
      level = 'watch';
    } else if (status === 'contained' && level === 'none') {
      level = 'contained';
    }
  }
  return level;
}

export interface ZoneHullRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Padded bounding box around member points (viewport px). Pure for tests. */
export function computeZoneHullRect(
  points: { x: number; y: number; sizePx: number }[],
  padding: number,
): ZoneHullRect | null {
  if (points.length === 0) {
    return null;
  }
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  let maxSize = 0;
  for (const point of points) {
    minX = Math.min(minX, point.x);
    minY = Math.min(minY, point.y);
    maxX = Math.max(maxX, point.x);
    maxY = Math.max(maxY, point.y);
    maxSize = Math.max(maxSize, point.sizePx);
  }
  const pad = padding + maxSize;
  return {
    left: minX - pad,
    top: minY - pad,
    width: maxX - minX + pad * 2,
    height: maxY - minY + pad * 2,
  };
}

interface ZoneFrameStyle {
  border: string;
  fill: string;
  label: string;
  dot: string;
  borderWidth: number;
}

// Hairline sector frames on the dark analysis plane. Colors mirror the
// --aegis-status-* tokens; the neutral frame stays whisper-quiet so hostile
// sectors are the loudest thing on the board.
const ZONE_FRAME_STYLES: Record<ZoneThreatLevel, ZoneFrameStyle> = {
  none: {
    border: 'rgba(148, 163, 184, 0.16)',
    fill: 'rgba(148, 163, 184, 0.035)',
    label: 'rgba(163, 175, 192, 0.62)',
    dot: 'rgba(148, 163, 184, 0.4)',
    borderWidth: 1,
  },
  contained: {
    border: 'rgba(154, 168, 255, 0.32)',
    fill: 'rgba(154, 168, 255, 0.045)',
    label: 'rgba(184, 194, 255, 0.85)',
    dot: '#9aa8ff',
    borderWidth: 1,
  },
  watch: {
    border: 'rgba(241, 194, 87, 0.38)',
    fill: 'rgba(241, 194, 87, 0.05)',
    label: 'rgba(241, 194, 87, 0.9)',
    dot: '#f1c257',
    borderWidth: 1.25,
  },
  hostile: {
    border: 'rgba(255, 112, 120, 0.5)',
    fill: 'rgba(255, 112, 120, 0.06)',
    label: 'rgba(255, 138, 145, 0.95)',
    dot: '#ff7078',
    borderWidth: 1.5,
  },
};

const HULL_PADDING_PX = 26;
const HULL_CORNER_RADIUS = 14;
const LABEL_FONT = '600 10px "JetBrains Mono", "Cascadia Mono", monospace';

function roundedRectPath(
  context: CanvasRenderingContext2D,
  rect: ZoneHullRect,
  radius: number,
): void {
  const r = Math.min(radius, rect.width / 2, rect.height / 2);
  const { left, top, width, height } = rect;
  context.beginPath();
  context.moveTo(left + r, top);
  context.lineTo(left + width - r, top);
  context.arcTo(left + width, top, left + width, top + r, r);
  context.lineTo(left + width, top + height - r);
  context.arcTo(left + width, top + height, left + width - r, top + height, r);
  context.lineTo(left + r, top + height);
  context.arcTo(left, top + height, left, top + height - r, r);
  context.lineTo(left, top + r);
  context.arcTo(left, top, left + r, top, r);
  context.closePath();
}

/**
 * Zone sector frames rendered on a dedicated canvas layer *below* Sigma's
 * edges, so the org's structure reads as a board of labeled territories the
 * graph sits on. Redraws only on Sigma render/resize events — eight rounded
 * rects and labels, no per-frame cost while idle.
 */
export class ZoneOverlay {
  private readonly sigma: Sigma;
  private readonly graph: Graph;
  private readonly canvas: HTMLCanvasElement;
  private zones: ZoneRenderState[] = [];
  private readonly handleRender = () => {
    this.draw();
  };
  private readonly handleResize = () => {
    this.resizeCanvas();
    this.draw();
  };

  constructor(sigma: Sigma, graph: Graph) {
    this.sigma = sigma;
    this.graph = graph;
    this.canvas = sigma.createCanvas('aegis-zone-hulls', { beforeLayer: 'edges' });
    this.canvas.setAttribute('aria-hidden', 'true');
    this.canvas.style.pointerEvents = 'none';
    this.resizeCanvas();
    sigma.on('afterRender', this.handleRender);
    sigma.on('resize', this.handleResize);
  }

  setZones(zones: ZoneRenderState[]): void {
    this.zones = zones;
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

    for (const zone of this.zones) {
      const points: { x: number; y: number; sizePx: number }[] = [];
      for (const memberId of zone.memberIds) {
        if (!this.graph.hasNode(memberId)) {
          continue;
        }
        const x = this.graph.getNodeAttribute(memberId, 'x') as number;
        const y = this.graph.getNodeAttribute(memberId, 'y') as number;
        const size = (this.graph.getNodeAttribute(memberId, 'size') as number | undefined) ?? 8;
        const viewport = this.sigma.graphToViewport({ x, y });
        points.push({ x: viewport.x, y: viewport.y, sizePx: this.sigma.scaleSize(size) });
      }
      const rect = computeZoneHullRect(points, HULL_PADDING_PX);
      if (!rect) {
        continue;
      }

      const style = ZONE_FRAME_STYLES[zone.threat];
      roundedRectPath(context, rect, HULL_CORNER_RADIUS);
      context.fillStyle = style.fill;
      context.fill();
      context.strokeStyle = style.border;
      context.lineWidth = style.borderWidth;
      context.stroke();

      // Sector eyebrow: status dot + zone name + member count, drawn inside
      // the frame's top-left corner (an outside label clips when the sector
      // sits at the canvas edge) so zones stay navigable even when node
      // labels LOD out.
      context.save();
      context.font = LABEL_FONT;
      if ('letterSpacing' in context) {
        (context as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = '1.5px';
      }
      const labelX = rect.left + 12;
      const labelY = rect.top + 18;
      context.beginPath();
      context.arc(labelX + 3, labelY - 3.5, 3, 0, Math.PI * 2);
      context.fillStyle = style.dot;
      context.fill();
      context.fillStyle = style.label;
      context.fillText(`${zone.label} · ${String(zone.memberIds.length)}`, labelX + 11, labelY);
      context.restore();
    }
  }

  dispose(): void {
    this.sigma.off('afterRender', this.handleRender);
    this.sigma.off('resize', this.handleResize);
    // The canvas itself is owned by Sigma's layer system and is removed by
    // sigma.kill().
  }
}
