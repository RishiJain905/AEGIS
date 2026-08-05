import type Graph from 'graphology';
import type Sigma from 'sigma';

import { overlayCanvasMetrics, syncOverlayCanvas } from './overlay-canvas';

/** Statuses that emit a persistent halo. `normal` nodes stay quiet. */
export type SignalStatus = 'suspicious' | 'under_investigation' | 'contained' | 'compromised';

export interface NodeSignal {
  id: string;
  status: SignalStatus;
}

export const REVEAL_PULSE_MS = 1600;
/** Reduced motion: the static reveal ring stays up this long, then vanishes. */
export const REVEAL_STATIC_MS = 4000;

/** 0..1 animation progress of a reveal pulse; 1 = finished. Pure for tests. */
export function revealPulseProgress(now: number, startedAt: number): number {
  return Math.min(1, Math.max(0, (now - startedAt) / REVEAL_PULSE_MS));
}

interface RevealPulse {
  nodeId: string;
  startedAt: number;
}

const STATUS_HALOS: Record<SignalStatus, { color: string; glow: number; ring: number }> = {
  suspicious: { color: '241, 194, 87', glow: 0.26, ring: 0.6 },
  under_investigation: { color: '104, 208, 238', glow: 0.14, ring: 0.7 },
  contained: { color: '154, 168, 255', glow: 0.1, ring: 0.8 },
  compromised: { color: '255, 112, 120', glow: 0.45, ring: 0.95 },
};

/**
 * Persistent status halos and the fog-of-war reveal pulse, on a canvas layer
 * between Sigma's edges and nodes. Halos are static (redrawn only on Sigma
 * renders); the reveal pulse runs a short self-owned rAF loop that touches
 * only this canvas — no WebGL re-render, no per-frame graph work. Under
 * reduced motion the pulse is replaced by a static double ring that appears
 * and later disappears with zero animation.
 */
export class SignalOverlay {
  private readonly sigma: Sigma;
  private readonly graph: Graph;
  private readonly canvas: HTMLCanvasElement;
  private signals: NodeSignal[] = [];
  private pulses: RevealPulse[] = [];
  private reducedMotion: boolean;
  private frameHandle: number | null = null;
  private staticExpiryTimer: number | null = null;
  private readonly handleRender = () => {
    this.draw(performance.now());
  };
  private readonly handleResize = () => {
    this.resizeCanvas();
    this.draw(performance.now());
  };

  constructor(sigma: Sigma, graph: Graph, reducedMotion: boolean) {
    this.sigma = sigma;
    this.graph = graph;
    this.reducedMotion = reducedMotion;
    this.canvas = sigma.createCanvas('aegis-signals', { beforeLayer: 'nodes' });
    this.canvas.setAttribute('aria-hidden', 'true');
    this.canvas.style.pointerEvents = 'none';
    this.resizeCanvas();
    sigma.on('afterRender', this.handleRender);
    sigma.on('resize', this.handleResize);
  }

  setReducedMotion(reduced: boolean): void {
    this.reducedMotion = reduced;
    this.syncDriver();
  }

  setSignals(signals: NodeSignal[]): void {
    this.signals = signals;
  }

  /** The detection beat: revealed nodes get an expanding critical-red pulse
   * (or a static ring under reduced motion). */
  addReveals(nodeIds: string[], now: number = performance.now()): void {
    if (nodeIds.length === 0) {
      return;
    }
    for (const nodeId of nodeIds) {
      this.pulses.push({ nodeId, startedAt: now });
    }
    this.syncDriver();
    this.draw(now);
  }

  getActivePulseNodeIds(): string[] {
    return this.pulses.map((pulse) => pulse.nodeId);
  }

  private syncDriver(): void {
    if (this.pulses.length === 0) {
      this.stopDriver();
      return;
    }
    if (this.reducedMotion) {
      this.stopAnimationFrame();
      if (this.staticExpiryTimer === null) {
        this.staticExpiryTimer = window.setTimeout(() => {
          this.staticExpiryTimer = null;
          this.expirePulses(performance.now(), REVEAL_STATIC_MS);
          this.draw(performance.now());
          this.syncDriver();
        }, REVEAL_STATIC_MS);
      }
      return;
    }
    if (this.frameHandle !== null) {
      return;
    }
    const step = () => {
      const now = performance.now();
      this.expirePulses(now, REVEAL_PULSE_MS);
      this.draw(now);
      if (this.pulses.length > 0 && !this.reducedMotion) {
        this.frameHandle = requestAnimationFrame(step);
      } else {
        this.frameHandle = null;
      }
    };
    this.frameHandle = requestAnimationFrame(step);
  }

  private expirePulses(now: number, lifetimeMs: number): void {
    this.pulses = this.pulses.filter((pulse) => now - pulse.startedAt < lifetimeMs);
  }

  private stopAnimationFrame(): void {
    if (this.frameHandle !== null) {
      cancelAnimationFrame(this.frameHandle);
      this.frameHandle = null;
    }
  }

  private stopDriver(): void {
    this.stopAnimationFrame();
    if (this.staticExpiryTimer !== null) {
      window.clearTimeout(this.staticExpiryTimer);
      this.staticExpiryTimer = null;
    }
  }

  private resizeCanvas(): void {
    syncOverlayCanvas(this.canvas, overlayCanvasMetrics(this.sigma));
  }

  private nodeViewpoint(nodeId: string): { x: number; y: number; sizePx: number } | null {
    if (!this.graph.hasNode(nodeId)) {
      return null;
    }
    const x = this.graph.getNodeAttribute(nodeId, 'x') as number;
    const y = this.graph.getNodeAttribute(nodeId, 'y') as number;
    const size = (this.graph.getNodeAttribute(nodeId, 'size') as number | undefined) ?? 8;
    const viewport = this.sigma.graphToViewport({ x, y });
    return { x: viewport.x, y: viewport.y, sizePx: this.sigma.scaleSize(size) };
  }

  draw(now: number): void {
    const context = this.canvas.getContext('2d');
    if (!context) {
      return;
    }
    // Sigma emits no 'resize' when the container size is unchanged, so the
    // canvas is re-checked here: on a 2D/3D remount the renderer mounts at its
    // final size and this is the only place the overlay learns its geometry.
    const { width, height } = this.sigma.getDimensions();
    this.resizeCanvas();
    context.clearRect(0, 0, width, height);

    for (const signal of this.signals) {
      const point = this.nodeViewpoint(signal.id);
      if (!point) {
        continue;
      }
      const halo = STATUS_HALOS[signal.status];
      const glowRadius = point.sizePx * 2.6;

      if (halo.glow > 0) {
        const gradient = context.createRadialGradient(
          point.x,
          point.y,
          point.sizePx * 0.4,
          point.x,
          point.y,
          glowRadius,
        );
        gradient.addColorStop(0, `rgba(${halo.color}, ${String(halo.glow)})`);
        gradient.addColorStop(1, `rgba(${halo.color}, 0)`);
        context.beginPath();
        context.arc(point.x, point.y, glowRadius, 0, Math.PI * 2);
        context.fillStyle = gradient;
        context.fill();
      }

      context.beginPath();
      context.arc(point.x, point.y, point.sizePx + 3.5, 0, Math.PI * 2);
      context.strokeStyle = `rgba(${halo.color}, ${String(halo.ring)})`;
      context.lineWidth = signal.status === 'compromised' ? 2.25 : 1.25;
      if (signal.status === 'contained') {
        context.setLineDash([5, 4]);
      }
      context.stroke();
      context.setLineDash([]);
    }

    for (const pulse of this.pulses) {
      const point = this.nodeViewpoint(pulse.nodeId);
      if (!point) {
        continue;
      }
      if (this.reducedMotion) {
        // Static, motion-free detection marker: bright double ring.
        context.beginPath();
        context.arc(point.x, point.y, point.sizePx + 5, 0, Math.PI * 2);
        context.strokeStyle = 'rgba(255, 112, 120, 0.9)';
        context.lineWidth = 2;
        context.stroke();
        context.beginPath();
        context.arc(point.x, point.y, point.sizePx + 12, 0, Math.PI * 2);
        context.strokeStyle = 'rgba(255, 112, 120, 0.4)';
        context.lineWidth = 1.25;
        context.stroke();
        continue;
      }
      const progress = revealPulseProgress(now, pulse.startedAt);
      const fade = (1 - progress) ** 1.5;
      // Two expanding shockwave rings, the second launching at 35% of the run.
      for (const [delay, weight] of [
        [0, 1],
        [0.35, 0.6],
      ] as const) {
        const local = Math.min(1, Math.max(0, (progress - delay) / (1 - delay)));
        if (local <= 0 || local >= 1) {
          continue;
        }
        const radius = point.sizePx + local * point.sizePx * 7;
        context.beginPath();
        context.arc(point.x, point.y, radius, 0, Math.PI * 2);
        context.strokeStyle = `rgba(255, 112, 120, ${String((1 - local) * 0.9 * weight)})`;
        context.lineWidth = 2 * (1 - local) + 0.5;
        context.stroke();
      }
      // Center flash that decays over the full pulse.
      const flash = context.createRadialGradient(
        point.x,
        point.y,
        0,
        point.x,
        point.y,
        point.sizePx * 2.4,
      );
      flash.addColorStop(0, `rgba(255, 138, 145, ${String(fade * 0.5)})`);
      flash.addColorStop(1, 'rgba(255, 138, 145, 0)');
      context.beginPath();
      context.arc(point.x, point.y, point.sizePx * 2.4, 0, Math.PI * 2);
      context.fillStyle = flash;
      context.fill();
    }
  }

  dispose(): void {
    this.stopDriver();
    this.sigma.off('afterRender', this.handleRender);
    this.sigma.off('resize', this.handleResize);
    this.pulses = [];
    this.signals = [];
    // Canvas element removal is owned by sigma.kill().
  }
}
