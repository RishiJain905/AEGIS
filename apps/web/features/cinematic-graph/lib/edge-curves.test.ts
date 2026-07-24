import { describe, expect, it } from 'vitest';

import { edgeArcKind, edgeArcLift, edgeArcPoints, edgeArcSegments } from './edge-curves';

const A = { x: 0, y: 30, z: 0 };
const B = { x: 200, y: 50, z: -120 };

describe('edge arcs', () => {
  it('classifies same-zone edges as intra and everything else as inter', () => {
    expect(edgeArcKind('zone:a', 'zone:a')).toBe('intra');
    expect(edgeArcKind('zone:a', 'zone:b')).toBe('inter');
    expect(edgeArcKind(null, null)).toBe('inter');
    expect(edgeArcKind('zone:a', null)).toBe('inter');
  });

  it('starts and ends exactly at the node positions', () => {
    const points = edgeArcPoints(A, B, 'inter');
    expect(points[0]).toEqual(A);
    expect(points[points.length - 1]).toEqual(B);
    expect(points).toHaveLength(edgeArcSegments('inter') + 1);
  });

  it('lifts inter-zone highways higher than intra-zone links', () => {
    expect(edgeArcLift(A, B, 'inter')).toBeGreaterThan(edgeArcLift(A, B, 'intra'));
  });

  it('keeps the apex above both endpoints and within the lift envelope', () => {
    const points = edgeArcPoints(A, B, 'inter');
    const apex = Math.max(...points.map((point) => point.y));
    expect(apex).toBeGreaterThan(Math.max(A.y, B.y));
    expect(apex).toBeLessThanOrEqual(Math.max(A.y, B.y) + 175);
  });

  it('is deterministic', () => {
    expect(edgeArcPoints(A, B, 'intra')).toEqual(edgeArcPoints(A, B, 'intra'));
  });
});
