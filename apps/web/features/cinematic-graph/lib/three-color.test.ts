import { describe, expect, it, vi } from 'vitest';

import { resolveThreeColor } from '@/features/cinematic-graph/lib/three-color';

describe('resolveThreeColor', () => {
  it('separates rgba alpha without passing rgba syntax to THREE.Color', () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    const resolved = resolveThreeColor('rgba(239, 68, 68, 0.62)');

    expect(resolved.color.getHexString()).toBe('ef4444');
    expect(resolved.opacity).toBeCloseTo(0.62, 4);
    expect(warning).not.toHaveBeenCalled();
    warning.mockRestore();
  });

  it('separates alpha-hex opacity and reuses the cached result', () => {
    const first = resolveThreeColor('#ef444488');
    const second = resolveThreeColor('#ef444488');

    expect(first.color.getHexString()).toBe('ef4444');
    expect(first.opacity).toBeCloseTo(0.5333, 3);
    expect(second).toBe(first);
  });
});
