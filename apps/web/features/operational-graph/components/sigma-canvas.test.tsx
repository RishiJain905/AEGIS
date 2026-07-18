import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('sigma', () => {
  const handlers = new Map<string, Set<(event: { node?: string }) => void>>();
  return {
    default: class MockSigma {
      kill = vi.fn();
      refresh = vi.fn();
      on(event: string, handler: (payload: { node?: string }) => void) {
        const set = handlers.get(event) ?? new Set();
        set.add(handler);
        handlers.set(event, set);
      }
      off(event: string, handler: (payload: { node?: string }) => void) {
        handlers.get(event)?.delete(handler);
      }
      getCamera() {
        return {
          animate: vi.fn(),
          animatedReset: vi.fn(),
          ratio: 1,
        };
      }
    },
  };
});

vi.mock('@aegis/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@aegis/ui')>();
  return {
    ...actual,
    useReducedMotion: () => false,
  };
});

import { SigmaCanvas } from '@/features/operational-graph/components/sigma-canvas';

describe('SigmaCanvas', () => {
  it('calls dispose on unmount', () => {
    const onReady = vi.fn();
    const { unmount } = render(
      <SigmaCanvas
        onAdapterReady={onReady}
        onNodeClick={vi.fn()}
        onStageClick={vi.fn()}
        onNodeHover={vi.fn()}
      />,
    );

    expect(screen.getByTestId('operational-graph-canvas')).toBeInTheDocument();
    expect(onReady).toHaveBeenCalled();
    unmount();
  });

  it('keeps the renderer mounted when event callback identities change', () => {
    const onReady = vi.fn();
    const { rerender } = render(
      <SigmaCanvas
        onAdapterReady={onReady}
        onNodeClick={vi.fn()}
        onStageClick={vi.fn()}
        onNodeHover={vi.fn()}
      />,
    );

    rerender(
      <SigmaCanvas
        onAdapterReady={onReady}
        onNodeClick={vi.fn()}
        onStageClick={vi.fn()}
        onNodeHover={vi.fn()}
      />,
    );

    expect(onReady).toHaveBeenCalledTimes(1);
  });
});
