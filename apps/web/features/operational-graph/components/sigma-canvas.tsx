'use client';

import { useEffect, useRef, useState } from 'react';

import { useReducedMotion } from '@aegis/ui';

import { probeCapabilityReport } from '@/features/cinematic-graph/lib/capability';

import {
  createSigmaOperationalGraphAdapter,
  type SigmaOperationalGraphAdapter,
} from '../adapters/sigma-operational-graph-adapter';
import { resolveEdgeFlowProfile, type EdgeFlowProfile } from '../semantic/graph-semantic-styles';

/** Sigma's node mouse-event payload, narrowed to the fields this canvas uses. */
interface SigmaNodeMouseEvent {
  node: string;
  event: { x: number; y: number; original: Event; preventSigmaDefault: () => void };
}

export interface SigmaCanvasProps {
  onAdapterReady: (adapter: SigmaOperationalGraphAdapter) => void;
  onNodeClick: (nodeId: string) => void;
  onStageClick: () => void;
  onNodeHover: (nodeId: string | null) => void;
  /** Right-click on a node, with the pointer position relative to the canvas container. */
  onNodeRightClick?: (nodeId: string, position: { x: number; y: number }) => void;
  className?: string;
}

export function SigmaCanvas({
  onAdapterReady,
  onNodeClick,
  onStageClick,
  onNodeHover,
  onNodeRightClick,
  className,
}: SigmaCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const adapterRef = useRef<SigmaOperationalGraphAdapter | null>(null);
  const reducedMotion = useReducedMotion();
  const initialReducedMotionRef = useRef(reducedMotion);
  const callbacksRef = useRef({
    onAdapterReady,
    onNodeClick,
    onStageClick,
    onNodeHover,
    onNodeRightClick,
  });
  callbacksRef.current = {
    onAdapterReady,
    onNodeClick,
    onStageClick,
    onNodeHover,
    onNodeRightClick,
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const adapter = createSigmaOperationalGraphAdapter(container, initialReducedMotionRef.current);
    adapterRef.current = adapter;
    const sigma = adapter.mount();

    const handleNodeClick = (event: { node: string }) => {
      callbacksRef.current.onNodeClick(event.node);
    };
    const handleStageClick = () => {
      callbacksRef.current.onStageClick();
    };
    const handleEnterNode = (event: { node: string }) => {
      callbacksRef.current.onNodeHover(event.node);
    };
    const handleLeaveNode = () => {
      callbacksRef.current.onNodeHover(null);
    };
    const handleRightClickNode = (payload: SigmaNodeMouseEvent) => {
      // Suppress both the browser menu and Sigma's own right-drag pan for this gesture.
      payload.event.original.preventDefault();
      payload.event.preventSigmaDefault();
      callbacksRef.current.onNodeRightClick?.(payload.node, {
        x: payload.event.x,
        y: payload.event.y,
      });
    };

    sigma.on('clickNode', handleNodeClick);
    sigma.on('clickStage', handleStageClick);
    sigma.on('enterNode', handleEnterNode);
    sigma.on('leaveNode', handleLeaveNode);
    sigma.on('rightClickNode', handleRightClickNode);

    // The container may have zero size at mount (mode toggle mid-layout) or
    // change size later; resize the renderer whenever real dimensions arrive
    // so the graph reliably appears without a manual window resize.
    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        adapterRef.current?.resize();
      });
      resizeObserver.observe(container);
    }

    callbacksRef.current.onAdapterReady(adapter);

    return () => {
      resizeObserver?.disconnect();
      sigma.off('clickNode', handleNodeClick);
      sigma.off('clickStage', handleStageClick);
      sigma.off('enterNode', handleEnterNode);
      sigma.off('leaveNode', handleLeaveNode);
      sigma.off('rightClickNode', handleRightClickNode);
      adapter.dispose();
      adapterRef.current = null;
    };
  }, []);

  useEffect(() => {
    adapterRef.current?.setReducedMotion(reducedMotion);
  }, [reducedMotion]);

  // §7.9 gate, applied independently in the 2D renderer: the live
  // `prefers-reduced-motion` media query (via useReducedMotion) forces fully
  // static edges, and the probed render tier maps HIGH → full flow, MEDIUM →
  // coarse (shared phase), LOW/FALLBACK_2D → static.
  const [flowTier] = useState(() => probeCapabilityReport().recommendedTier);
  useEffect(() => {
    const profile: EdgeFlowProfile = resolveEdgeFlowProfile(flowTier, reducedMotion);
    adapterRef.current?.setEdgeFlowProfile(profile);
  }, [flowTier, reducedMotion]);

  return (
    <div
      ref={containerRef}
      className={className}
      data-testid="operational-graph-canvas"
      role="img"
      aria-label="Operational investigation graph canvas"
      onContextMenu={(event) => {
        // The node menu is opened from Sigma's rightClickNode; never let the native
        // browser menu cover it (or appear when the operator misses a node).
        event.preventDefault();
      }}
      style={{ width: '100%', height: '100%', minHeight: '16rem' }}
    />
  );
}
