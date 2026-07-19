import { z } from 'zod';

export const SCENE_EDGE_SCHEMA_VERSION = 1;

export const sceneEdgeSchema = z
  .object({
    schemaVersion: z.literal(SCENE_EDGE_SCHEMA_VERSION),
    id: z.string().min(1),
    sourceId: z.string().min(1),
    targetId: z.string().min(1),
    relationshipType: z.string(),
    directed: z.boolean(),
    confidence: z.number().min(0).max(1),
    riskContribution: z.number().min(0).max(1),
    eventCount: z.number().int().nonnegative(),
    color: z.string(),
    opacity: z.number().min(0).max(1),
    width: z.number().positive(),
    highlighted: z.boolean(),
    dimmed: z.boolean(),
    // §7.4/§7.9 derived presentation fields (dashed containment + alive-flow
    // parameters). Presentation-only: pulseAt is a shared-animation-clock
    // timestamp (NO_PULSE sentinel when the edge never pulsed) and is never
    // part of any deterministic projection tests hash.
    dashed: z.boolean(),
    flowSpeed: z.number().min(0),
    flowAmplitude: z.number().min(0).max(1),
    pulseAt: z.number(),
  })
  .strict();

export type SceneEdge = z.infer<typeof sceneEdgeSchema>;

export function parseSceneEdge(data: unknown): SceneEdge {
  return sceneEdgeSchema.parse(data);
}
