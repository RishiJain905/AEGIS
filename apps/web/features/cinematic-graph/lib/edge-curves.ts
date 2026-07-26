/**
 * Arc geometry for the bastion-ring edge system. Intra-zone links stay low
 * over their platform; inter-zone links rise into elevated highways that
 * cross the dark ring interior, so lateral movement between zones reads as a
 * bright trace over the void. Pure math — endpoints are the authoritative
 * node positions, only the path between them is presentation.
 */

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export type EdgeArcKind = 'intra' | 'inter';

const INTRA_SEGMENTS = 10;
const INTER_SEGMENTS = 22;

export function edgeArcKind(sourceZoneId: string | null, targetZoneId: string | null): EdgeArcKind {
  if (sourceZoneId !== null && sourceZoneId === targetZoneId) {
    return 'intra';
  }
  return 'inter';
}

export function edgeArcLift(source: Vec3, target: Vec3, kind: EdgeArcKind): number {
  const run = Math.hypot(target.x - source.x, target.z - source.z);
  if (kind === 'intra') {
    return 10 + run * 0.16;
  }
  return Math.min(175, Math.max(48, run * 0.3));
}

export function edgeArcSegments(kind: EdgeArcKind): number {
  return kind === 'intra' ? INTRA_SEGMENTS : INTER_SEGMENTS;
}

/**
 * Quadratic bezier from source to target with an apex lifted above the higher
 * endpoint. First and last samples are exactly the endpoints.
 */
export function edgeArcPoints(
  source: Vec3,
  target: Vec3,
  kind: EdgeArcKind,
  segments = edgeArcSegments(kind),
): Vec3[] {
  const lift = edgeArcLift(source, target, kind);
  const control: Vec3 = {
    x: (source.x + target.x) / 2,
    y: Math.max(source.y, target.y) + lift,
    z: (source.z + target.z) / 2,
  };

  const points: Vec3[] = [];
  for (let index = 0; index <= segments; index += 1) {
    const t = index / segments;
    const u = 1 - t;
    points.push({
      x: u * u * source.x + 2 * u * t * control.x + t * t * target.x,
      y: u * u * source.y + 2 * u * t * control.y + t * t * target.y,
      z: u * u * source.z + 2 * u * t * control.z + t * t * target.z,
    });
  }
  // Guarantee exact endpoints despite floating-point accumulation.
  points[0] = { ...source };
  points[segments] = { ...target };
  return points;
}
