import { z } from 'zod';

export const SCENE_ZONE_SCHEMA_VERSION = 1;

/**
 * A sector platform of the bastion ring: derived, read-only presentation of a
 * graph cluster (or the unassigned pool). Placement geometry comes from the
 * deterministic zone layout; `alertLevel` is a rollup of the zone's disclosed
 * node statuses only — fog of war never leaks through a platform tint.
 */
export const sceneZoneSchema = z
  .object({
    schemaVersion: z.literal(SCENE_ZONE_SCHEMA_VERSION),
    id: z.string().min(1),
    label: z.string().min(1),
    center: z
      .object({
        x: z.number(),
        y: z.number(),
        z: z.number(),
      })
      .strict(),
    radius: z.number().positive(),
    angle: z.number(),
    alertLevel: z.enum(['calm', 'guarded', 'elevated', 'critical']),
    nodeCount: z.number().int().min(0),
  })
  .strict();

export type SceneZone = z.infer<typeof sceneZoneSchema>;

export function parseSceneZone(data: unknown): SceneZone {
  return sceneZoneSchema.parse(data);
}
