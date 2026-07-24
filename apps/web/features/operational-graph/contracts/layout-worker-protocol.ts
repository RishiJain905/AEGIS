import { z } from 'zod';

import { graphRevisionSchema } from './graph-revision';

export const LAYOUT_WORKER_PROTOCOL_VERSION = 1 as const;

export const LayoutWorkerErrorCode = {
  VALIDATION_FAILED: 'VALIDATION_FAILED',
  CANCELLED: 'CANCELLED',
  INTERNAL: 'INTERNAL',
} as const;

export type LayoutWorkerErrorCodeValue =
  (typeof LayoutWorkerErrorCode)[keyof typeof LayoutWorkerErrorCode];

export const layoutWorkerErrorCodeSchema = z.enum([
  LayoutWorkerErrorCode.VALIDATION_FAILED,
  LayoutWorkerErrorCode.CANCELLED,
  LayoutWorkerErrorCode.INTERNAL,
]);

export const layoutModeSchema = z.enum(['full', 'incremental']);

export type LayoutMode = z.infer<typeof layoutModeSchema>;

export const layoutPositionSchema = z
  .object({
    x: z.number(),
    y: z.number(),
  })
  .strict();

export type LayoutPosition = z.infer<typeof layoutPositionSchema>;

export const layoutWorkerNodeSchema = z
  .object({
    id: z.string(),
    clusterId: z.string().nullable(),
    pinned: z.boolean(),
    x: z.number().optional(),
    y: z.number().optional(),
    weight: z.number().min(0).optional(),
  })
  .strict();

export type LayoutWorkerNode = z.infer<typeof layoutWorkerNodeSchema>;

export const layoutWorkerEdgeSchema = z
  .object({
    source: z.string(),
    target: z.string(),
    weight: z.number().min(0),
  })
  .strict();

export type LayoutWorkerEdge = z.infer<typeof layoutWorkerEdgeSchema>;

/** Containment disc for one zone: the force pass may refine node placement
 * inside the disc but never move a node out of its zone sector. */
export const layoutZoneConstraintSchema = z
  .object({
    x: z.number(),
    y: z.number(),
    radius: z.number().positive(),
  })
  .strict();

export type LayoutZoneConstraint = z.infer<typeof layoutZoneConstraintSchema>;

export const layoutWorkerSettingsSchema = z
  .object({
    iterations: z.number().int().min(1).max(500),
    gravity: z.number().min(0).max(10),
    scalingRatio: z.number().min(1).max(100),
    barnesHutOptimize: z.boolean(),
    slowDown: z.number().min(0.1).max(10),
  })
  .strict();

export type LayoutWorkerSettings = z.infer<typeof layoutWorkerSettingsSchema>;

// Zone containment (zoneConstraints) replaces gravity as the anti-scatter
// force, so gravity stays near zero — any global pull toward the origin is
// exactly the central-hairball failure mode. Repulsion is moderate: it only
// has to spread nodes within a zone disc, never across the whole board.
export const defaultLayoutWorkerSettings: LayoutWorkerSettings = {
  iterations: 140,
  gravity: 0.02,
  scalingRatio: 30,
  barnesHutOptimize: true,
  slowDown: 5,
};

export const layoutWorkerRequestSchema = z
  .object({
    protocolVersion: z.literal(LAYOUT_WORKER_PROTOCOL_VERSION),
    requestId: z.string().min(1),
    graphRevision: graphRevisionSchema,
    runId: z.string(),
    mode: layoutModeSchema,
    nodes: z.array(layoutWorkerNodeSchema),
    edges: z.array(layoutWorkerEdgeSchema),
    seedPositions: z.record(z.string(), layoutPositionSchema),
    zoneConstraints: z.record(z.string(), layoutZoneConstraintSchema).optional(),
    settings: layoutWorkerSettingsSchema,
  })
  .strict();

export type LayoutWorkerRequest = z.infer<typeof layoutWorkerRequestSchema>;

export const LayoutWorkerResultStatus = {
  PROGRESS: 'progress',
  COMPLETE: 'complete',
  CANCELLED: 'cancelled',
  ERROR: 'error',
} as const;

export type LayoutWorkerResultStatusValue =
  (typeof LayoutWorkerResultStatus)[keyof typeof LayoutWorkerResultStatus];

export const layoutWorkerResultStatusSchema = z.enum([
  LayoutWorkerResultStatus.PROGRESS,
  LayoutWorkerResultStatus.COMPLETE,
  LayoutWorkerResultStatus.CANCELLED,
  LayoutWorkerResultStatus.ERROR,
]);

export const layoutWorkerResultSchema = z
  .object({
    protocolVersion: z.literal(LAYOUT_WORKER_PROTOCOL_VERSION),
    requestId: z.string().min(1),
    graphRevision: graphRevisionSchema,
    status: layoutWorkerResultStatusSchema,
    positions: z.record(z.string(), layoutPositionSchema).optional(),
    iterationsCompleted: z.number().int().nonnegative(),
    durationMs: z.number().nonnegative(),
    errorCode: layoutWorkerErrorCodeSchema.optional(),
    errorMessage: z.string().optional(),
  })
  .strict();

export type LayoutWorkerResult = z.infer<typeof layoutWorkerResultSchema>;

export const layoutWorkerCancelMessageSchema = z
  .object({
    type: z.literal('cancel'),
    requestId: z.string().min(1),
  })
  .strict();

export type LayoutWorkerCancelMessage = z.infer<typeof layoutWorkerCancelMessageSchema>;

export const layoutWorkerShutdownMessageSchema = z
  .object({
    type: z.literal('shutdown'),
  })
  .strict();

export type LayoutWorkerShutdownMessage = z.infer<typeof layoutWorkerShutdownMessageSchema>;

export const layoutWorkerInboundMessageSchema = z.union([
  layoutWorkerRequestSchema,
  layoutWorkerCancelMessageSchema,
  layoutWorkerShutdownMessageSchema,
]);

export type LayoutWorkerInboundMessage = z.infer<typeof layoutWorkerInboundMessageSchema>;

export function parseLayoutWorkerRequest(data: unknown): LayoutWorkerRequest {
  return layoutWorkerRequestSchema.parse(data);
}

export function parseLayoutWorkerResult(data: unknown): LayoutWorkerResult {
  return layoutWorkerResultSchema.parse(data);
}

export function parseLayoutWorkerInboundMessage(data: unknown): LayoutWorkerInboundMessage {
  return layoutWorkerInboundMessageSchema.parse(data);
}
