'use client';

import { GraphViewMode, type GraphViewModeValue } from '../contracts/graph-view-mode';
import { RenderQualityTier } from '../contracts/render-quality-tier';
import { useCinematicGraphStore } from '../stores/cinematic-graph-store';

export function GraphViewModeToggle() {
  const viewMode = useCinematicGraphStore((s) => s.viewMode);
  const qualityTier = useCinematicGraphStore((s) => s.qualityTier);
  const setViewMode = useCinematicGraphStore((s) => s.setViewMode);
  const threeDisabled = qualityTier === RenderQualityTier.FALLBACK_2D;

  const setMode = (mode: GraphViewModeValue) => {
    if (mode === GraphViewMode.THREE_D && threeDisabled) {
      return;
    }
    setViewMode(mode);
  };

  return (
    <div
      className="inline-flex rounded border border-[var(--aegis-border)] p-0.5 text-xs"
      role="group"
      aria-label="Graph view mode"
      data-testid="graph-view-mode-toggle"
    >
      <button
        type="button"
        className={`rounded px-2 py-1 ${viewMode === GraphViewMode.TWO_D ? 'bg-[var(--aegis-surface-elevated)] font-medium' : ''}`}
        aria-pressed={viewMode === GraphViewMode.TWO_D}
        data-testid="graph-view-mode-2d"
        onClick={() => setMode(GraphViewMode.TWO_D)}
      >
        2D
      </button>
      <button
        type="button"
        className={`rounded px-2 py-1 ${viewMode === GraphViewMode.THREE_D ? 'bg-[var(--aegis-surface-elevated)] font-medium' : ''}`}
        aria-pressed={viewMode === GraphViewMode.THREE_D}
        aria-disabled={threeDisabled}
        disabled={threeDisabled}
        title={
          threeDisabled
            ? '3D unavailable on this device — Sigma.js 2D remains available'
            : 'Open Three.js semantic renderer'
        }
        data-testid="graph-view-mode-3d"
        onClick={() => setMode(GraphViewMode.THREE_D)}
      >
        3D
      </button>
    </div>
  );
}
