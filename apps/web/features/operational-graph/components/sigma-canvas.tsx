'use client';

import { useEffect, useRef, useCallback } from 'react';

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

  const handleNodeClick = useCallback(
    (event: { node: string }) => {
      onNodeClick(event.node);
    },
    [onNodeClick],
  );

  const handleStageClick = useCallback(() => {
    onStageClick();
  }, [onStageClick]);

  const handleEnterNode = useCallback(
    (event: { node: string }) => {
      onNodeHover(event.node);
    },
    [onNodeHover],
  );

  const handleLeaveNode = useCallback(() => {
    onNodeHover(null);
  }, [onNodeHover]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const adapter = createSigmaOperationalGraphAdapter(container, reducedMotion);
    adapterRef.current = adapter;
    const sigma = adapter.mount();

    sigma.on('clickNode', handleNodeClick);
    sigma.on('clickStage', handleStageClick);
    sigma.on('enterNode', handleEnterNode);
    sigma.on('leaveNode', handleLeaveNode);

    onAdapterReady(adapter);

    return () => {
      sigma.off('clickNode', handleNodeClick);
      sigma.off('clickStage', handleStageClick);
      sigma.off('enterNode', handleEnterNode);
      sigma.off('leaveNode', handleLeaveNode);
      adapter.dispose();
      adapterRef.current = null;
    };
  }, [
    reducedMotion,
    onAdapterReady,
    handleNodeClick,
    handleStageClick,
    handleEnterNode,
    handleLeaveNode,
  ]);

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
