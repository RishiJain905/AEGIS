import { z } from 'zod';

export const SCENE_NODE_SCHEMA_VERSION = 1;

export const sceneNodeSchema = z
  .object({
    schemaVersion: z.literal(SCENE_NODE_SCHEMA_VERSION),
    id: z.string().min(1),
    label: z.string(),
    entityType: z.enum(['asset', 'cluster', 'presentation_cluster']),
    assetType: z.string().nullable(),
    clusterId: z.string().nullable(),
    riskScore: z.number().min(0).max(1),
    criticality: z.number().min(0).max(1),
    status: z.string(),
    position: z
      .object({
        x: z.number(),
        y: z.number(),
        z: z.number(),
      })
      .strict(),
    color: z.string(),
    statusColor: z.string(),
    riskHaloColor: z.string(),
    // §7.1/§7.2 derived presentation fields, resolved by the semantic scene
    // adapter from the shared risk/status token values — never stored on the
    // network/store node.
    emissiveColor: z.string(),
    sizeTier: z.number().positive(),
    glyphShape: z.enum(['circle', 'diamond', 'square', 'triangle', 'hexagon']),
    size: z.number().positive(),
    selected: z.boolean(),
    highlighted: z.boolean(),
    dimmed: z.boolean(),
    evidenceMarked: z.boolean(),
    incidentMarked: z.boolean(),
  })
  .strict();

export type SceneNode = z.infer<typeof sceneNodeSchema>;

export function parseSceneNode(data: unknown): SceneNode {
  return sceneNodeSchema.parse(data);
}
