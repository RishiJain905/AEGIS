import { GraphLayer, type GraphLayerValue } from '@aegis/graph-domain';
import { z } from 'zod';

import { defaultGraphCameraBookmark, graphCameraBookmarkSchema } from './graph-camera-bookmark';
import { defaultGraphSelection, graphSelectionSchema } from './graph-selection';

export const GRAPH_VISUAL_STATE_SCHEMA_VERSION = 1;

export const GraphHighlightMode = {
  NONE: 'none',
  NEIGHBORHOOD: 'neighborhood',
  PATH: 'path',
  INCIDENT: 'incident',
  DEPENDENCIES: 'dependencies',
} as const;

export type GraphHighlightModeValue = (typeof GraphHighlightMode)[keyof typeof GraphHighlightMode];

export const graphHighlightModeSchema = z.enum([
  GraphHighlightMode.NONE,
  GraphHighlightMode.NEIGHBORHOOD,
  GraphHighlightMode.PATH,
  GraphHighlightMode.INCIDENT,
  GraphHighlightMode.DEPENDENCIES,
]);

export const graphOverlayTogglesSchema = z
  .object({
    risk: z.boolean(),
    status: z.boolean(),
    evidence: z.boolean(),
    incident: z.boolean(),
  })
  .strict();

export type GraphOverlayToggles = z.infer<typeof graphOverlayTogglesSchema>;

export const defaultGraphOverlayToggles: GraphOverlayToggles = {
  risk: true,
  status: true,
  evidence: false,
  incident: true,
};

export const graphPredicateFilterSchema = z
  .object({
    nodeStatuses: z.array(z.string()).optional(),
    minRiskScore: z.number().min(0).max(1).optional(),
    relationshipTypes: z.array(z.string()).optional(),
    assetTypes: z.array(z.string()).optional(),
  })
  .strict();

export const graphFilterSetSchema = z
  .object({
    enabledLayers: z.array(z.string()).min(1),
    hiddenNodeIds: z.array(z.string()).optional(),
    hiddenEdgeIds: z.array(z.string()).optional(),
    predicate: graphPredicateFilterSchema.optional(),
  })
  .strict();

export type GraphFilterSetState = z.infer<typeof graphFilterSetSchema> & {
  enabledLayers: GraphLayerValue[];
};

export const graphVisualStateSchema = z
  .object({
    schemaVersion: z.literal(GRAPH_VISUAL_STATE_SCHEMA_VERSION),
    filterSet: graphFilterSetSchema,
    selection: graphSelectionSchema,
    hoveredNodeId: z.string().nullable(),
    highlightMode: graphHighlightModeSchema,
    highlightedNodeIds: z.array(z.string()),
    highlightedEdgeIds: z.array(z.string()),
    isolationActive: z.boolean(),
    searchQuery: z.string(),
    overlayToggles: graphOverlayTogglesSchema,
    nodePositions: z.record(z.string(), z.object({ x: z.number(), y: z.number() }).strict()),
    camera: graphCameraBookmarkSchema,
    pathModeActive: z.boolean(),
  })
  .strict();

export type GraphVisualState = z.infer<typeof graphVisualStateSchema>;

export const defaultGraphVisualState: GraphVisualState = {
  schemaVersion: GRAPH_VISUAL_STATE_SCHEMA_VERSION,
  filterSet: {
    enabledLayers: [
      GraphLayer.INFRASTRUCTURE,
      GraphLayer.ACTIVITY,
      GraphLayer.SECURITY_STATE,
      GraphLayer.INVESTIGATION,
      GraphLayer.PRESENTATION,
    ],
    predicate: {
      minRiskScore: 0,
    },
  },
  selection: defaultGraphSelection,
  hoveredNodeId: null,
  highlightMode: GraphHighlightMode.NONE,
  highlightedNodeIds: [],
  highlightedEdgeIds: [],
  isolationActive: false,
  searchQuery: '',
  overlayToggles: defaultGraphOverlayToggles,
  nodePositions: {},
  camera: defaultGraphCameraBookmark,
  pathModeActive: false,
};

export function parseGraphVisualState(data: unknown): GraphVisualState {
  return graphVisualStateSchema.parse(data);
}

export function assertExhaustiveHighlightMode(value: never): never {
  throw new Error(`Unhandled highlight mode: ${String(value)}`);
}
