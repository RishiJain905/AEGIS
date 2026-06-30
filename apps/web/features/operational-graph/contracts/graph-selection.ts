import { z } from 'zod';

export const GRAPH_SELECTION_SCHEMA_VERSION = 1;

export const graphSelectionSchema = z
  .object({
    schemaVersion: z.literal(GRAPH_SELECTION_SCHEMA_VERSION),
    primaryNodeId: z.string().nullable(),
    secondaryNodeId: z.string().nullable(),
    selectedEdgeId: z.string().nullable(),
  })
  .strict();

export type GraphSelection = z.infer<typeof graphSelectionSchema>;

export const defaultGraphSelection: GraphSelection = {
  schemaVersion: GRAPH_SELECTION_SCHEMA_VERSION,
  primaryNodeId: null,
  secondaryNodeId: null,
  selectedEdgeId: null,
};

export function parseGraphSelection(data: unknown): GraphSelection {
  return graphSelectionSchema.parse(data);
}
