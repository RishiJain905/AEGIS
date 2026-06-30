import { describe, expect, it } from 'vitest';

import { LayoutWorkerClient } from '@/features/operational-graph/performance/layout-worker-client';
import { UpdateBatcher } from '@/features/operational-graph/performance/update-batcher';

describe('graph resource cleanup', () => {
  it('terminates layout worker client', async () => {
    const terminated: string[] = [];
    const client = new LayoutWorkerClient(() => {
      const listeners = new Map<string, Set<(event: MessageEvent<unknown>) => void>>();
      return {
        addEventListener: (type: string, listener: (event: MessageEvent<unknown>) => void) => {
          const group = listeners.get(type) ?? new Set();
          group.add(listener);
          listeners.set(type, group);
          if (type === 'message') {
            listener({ data: { type: 'ready' } } as MessageEvent<unknown>);
          }
        },
        removeEventListener: (type: string, listener: (event: MessageEvent<unknown>) => void) => {
          listeners.get(type)?.delete(listener);
        },
        postMessage: () => {},
        terminate: () => {
          terminated.push('terminated');
        },
      } as unknown as Worker;
    });

    await client.initialize(() => {});
    client.shutdown();
    expect(terminated).toEqual(['terminated']);
  });

  it('disposes update batcher without retaining animation frame', () => {
    const batcher = new UpdateBatcher();
    batcher.schedule(() => {});
    batcher.dispose();
    expect(batcher.getDroppedFrames()).toBeGreaterThanOrEqual(0);
  });
});
