import { describe, expect, it, vi } from 'vitest';

import { UpdateBatcher } from './update-batcher';

describe('update batcher', () => {
  it('coalesces multiple scheduled updates into one frame task', () => {
    const callbacks: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callbacks.push(callback);
      return callbacks.length;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());

    const batcher = new UpdateBatcher({ frameBudgetMs: 1000 });
    let runs = 0;
    batcher.schedule(() => {
      runs += 1;
    });
    batcher.schedule(() => {
      runs += 1;
    });

    expect(callbacks).toHaveLength(1);
    callbacks[0]?.(0);
    expect(runs).toBe(1);

    batcher.dispose();
    vi.unstubAllGlobals();
  });
});
