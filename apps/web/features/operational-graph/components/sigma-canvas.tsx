'use client';

import { useEffect, useRef } from 'react';

import { useReducedMotion } from '@aegis/ui';

import {
  createSigmaOperationalGraphAdapter,
  type SigmaOperationalGraphAdapter,
} from '../adapters/sigma-operational-graph-adapter';

export interface SigmaCanvasProps {
  onAdapterReady: (adapter: SigmaOperationalGraphAdapter) => void;
  onNodeClick: (nodeId: string) => void;
  onStageClick: () => void;
  onNodeHover: (nodeId: string | null) => void;
  className?: string;
}

export function SigmaCanvas({
  onAdapterReady,
  onNodeClick,
  onStageClick,
  onNodeHover,
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
  });
  callbacksRef.current = {
    onAdapterReady,
    onNodeClick,
    onStageClick,
    onNodeHover,
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

    sigma.on('clickNode', handleNodeClick);
    sigma.on('clickStage', handleStageClick);
    sigma.on('enterNode', handleEnterNode);
    sigma.on('leaveNode', handleLeaveNode);

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
      adapter.dispose();
      adapterRef.current = null;
    };
  }, []);

  useEffect(() => {
    adapterRef.current?.setReducedMotion(reducedMotion);
  }, [reducedMotion]);

  return (
    <div
      ref={containerRef}
      className={className}
      data-testid="operational-graph-canvas"
      role="img"
      aria-label="Operational investigation graph canvas"
      style={{ width: '100%', height: '100%', minHeight: '16rem' }}
    />
  );
}
