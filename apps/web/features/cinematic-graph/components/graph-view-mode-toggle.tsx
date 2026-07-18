'use client';

import { useEffect } from 'react';

import { Button, useReducedMotion } from '@aegis/ui';

import { GraphViewMode, type GraphViewModeValue } from '../contracts/graph-view-mode';
import { RenderQualityTier } from '../contracts/render-quality-tier';
import { probeCapabilityReport } from '../lib/capability';
import { useCinematicGraphStore } from '../stores/cinematic-graph-store';

export function GraphViewModeToggle() {
  const viewMode = useCinematicGraphStore((s) => s.viewMode);
  const qualityTier = useCinematicGraphStore((s) => s.qualityTier);
  const capability = useCinematicGraphStore((s) => s.capability);
  const setViewMode = useCinematicGraphStore((s) => s.setViewMode);
  const setCapability = useCinematicGraphStore((s) => s.setCapability);
  const reducedMotion = useReducedMotion();
  const threeDisabled =
    qualityTier === RenderQualityTier.FALLBACK_2D &&
    capability.reasonCodes.includes('webgl-unavailable');

  useEffect(() => {
    const report = probeCapabilityReport({ reducedMotion });
    setCapability(report);
  }, [reducedMotion, setCapability]);

  const setMode = (mode: GraphViewModeValue) => {
    if (mode === GraphViewMode.THREE_D && threeDisabled) {
      return;
    }
    setViewMode(mode);
  };

  return (
    <div
      className="inline-flex rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-canvas)] p-1 shadow-[inset_0_1px_5px_rgb(0_0_0_/_0.28)]"
      role="group"
      aria-label="Graph view mode"
      data-testid="graph-view-mode-toggle"
    >
      <Button
        variant={viewMode === GraphViewMode.TWO_D ? 'secondary' : 'ghost'}
        size="sm"
        className="min-w-14 shadow-none"
        aria-pressed={viewMode === GraphViewMode.TWO_D}
        data-testid="graph-view-mode-2d"
        onClick={() => {
          setMode(GraphViewMode.TWO_D);
        }}
      >
        2D
      </Button>
      <Button
        variant={viewMode === GraphViewMode.THREE_D ? 'secondary' : 'ghost'}
        size="sm"
        className="min-w-14 shadow-none"
        aria-pressed={viewMode === GraphViewMode.THREE_D}
        aria-disabled={threeDisabled}
        disabled={threeDisabled}
        title={
          threeDisabled
            ? '3D unavailable on this device — Sigma.js 2D remains available'
            : 'Open Three.js semantic renderer'
        }
        data-testid="graph-view-mode-3d"
        onClick={() => {
          setMode(GraphViewMode.THREE_D);
        }}
      >
        3D
      </Button>
    </div>
  );
}
