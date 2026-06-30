import { z } from 'zod';

import {
  assetIdSchema,
  clusterIdSchema,
  edgeIdSchema,
  revisionSchema,
  runIdSchema,
  sequenceSchema,
  utcTimestampSchema,
} from './primitives';
import {
  GRAPH_DELTA_SCHEMA_VERSION,
  GRAPH_EDGE_SCHEMA_VERSION,
  GRAPH_NODE_SCHEMA_VERSION,
  GRAPH_PATH_QUERY_SCHEMA_VERSION,
  GRAPH_PATH_RESULT_SCHEMA_VERSION,
  GRAPH_SNAPSHOT_SCHEMA_VERSION,
} from './versioning';

export const EntityType = {
  ASSET: 'asset',
  CLUSTER: 'cluster',
} as const;

export const AssetType = {
  SERVICE: 'service',
  DEVICE: 'device',
  USER: 'user',
  IDENTITY: 'identity',
  DATABASE: 'database',
  CONTROL: 'control',
  AI_MODEL: 'ai_model',
} as const;

export const NodeStatus = {
  NORMAL: 'normal',
  SUSPICIOUS: 'suspicious',
  UNDER_INVESTIGATION: 'under_investigation',
  CONTAINED: 'contained',
  COMPROMISED: 'compromised',
} as const;

export const RelationshipType = {
  COMMUNICATED_WITH: 'COMMUNICATED_WITH',
  AUTHENTICATED_TO: 'AUTHENTICATED_TO',
  DEPENDS_ON: 'DEPENDS_ON',
  ADMINISTERS: 'ADMINISTERS',
  HOSTS: 'HOSTS',
} as const;

export const graphNodeSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    id: assetIdSchema,
    entityType: z.enum(['asset', 'cluster']),
    assetType: z.enum(['service', 'device', 'user', 'identity', 'database', 'control', 'ai_model']),
    label: z.string().min(1),
    clusterId: clusterIdSchema.optional(),
    riskScore: z.number().min(0).max(1),
    criticality: z.number().min(0).max(1),
    status: z.enum(['normal', 'suspicious', 'under_investigation', 'contained', 'compromised']),
    revision: revisionSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== GRAPH_NODE_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported graph node schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const graphEdgeSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    id: edgeIdSchema,
    source: assetIdSchema,
    target: assetIdSchema,
    relationshipType: z.enum([
      'COMMUNICATED_WITH',
      'AUTHENTICATED_TO',
      'DEPENDS_ON',
      'ADMINISTERS',
      'HOSTS',
    ]),
    directed: z.boolean(),
    confidence: z.number().min(0).max(1),
    riskContribution: z.number().min(0).max(1),
    firstSeenAt: utcTimestampSchema,
    lastSeenAt: utcTimestampSchema,
    eventCount: z.number().int().min(0),
    revision: revisionSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== GRAPH_EDGE_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported graph edge schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const graphClusterSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    id: clusterIdSchema,
    label: z.string().min(1),
    memberNodeIds: z.array(assetIdSchema),
    revision: revisionSchema,
  })
  .strict();

export const graphSnapshotSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema,
    sequence: sequenceSchema,
    capturedAt: utcTimestampSchema,
    nodes: z.array(graphNodeSchema),
    edges: z.array(graphEdgeSchema),
    clusters: z.array(graphClusterSchema).default([]),
    revision: revisionSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== GRAPH_SNAPSHOT_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported graph snapshot schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const GraphDeltaOperation = {
  UPSERT_NODE: 'upsert_node',
  UPSERT_EDGE: 'upsert_edge',
  DELETE_NODE: 'delete_node',
  DELETE_EDGE: 'delete_edge',
  UPSERT_CLUSTER: 'upsert_cluster',
} as const;

export const graphDeltaSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema,
    sequence: sequenceSchema,
    revision: revisionSchema,
    operation: z.enum([
      'upsert_node',
      'upsert_edge',
      'delete_node',
      'delete_edge',
      'upsert_cluster',
    ]),
    node: graphNodeSchema.optional(),
    edge: graphEdgeSchema.optional(),
    cluster: graphClusterSchema.optional(),
    targetId: z.union([assetIdSchema, edgeIdSchema]).optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== GRAPH_DELTA_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported graph delta schema version: ${String(value.schemaVersion)}`,
      });
      return;
    }
    if (value.operation === 'upsert_node' && value.node === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'upsert_node requires node payload',
      });
    }
    if (value.operation === 'upsert_edge' && value.edge === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'upsert_edge requires edge payload',
      });
    }
    if (
      (value.operation === 'delete_node' || value.operation === 'delete_edge') &&
      value.targetId === undefined
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'delete operations require targetId',
      });
    }
  });

export const graphPathQuerySchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema,
    sourceId: assetIdSchema,
    targetId: assetIdSchema,
    maxHops: z.number().int().min(1).max(32),
    relationshipTypes: z
      .array(
        z.enum(['COMMUNICATED_WITH', 'AUTHENTICATED_TO', 'DEPENDS_ON', 'ADMINISTERS', 'HOSTS']),
      )
      .default([]),
    directedOnly: z.boolean().default(true),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== GRAPH_PATH_QUERY_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported graph path query schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export const graphPathResultSchema = z
  .object({
    schemaVersion: z.number().int().min(1),
    runId: runIdSchema,
    sourceId: assetIdSchema,
    targetId: assetIdSchema,
    paths: z.array(z.array(assetIdSchema)),
    explanation: z.record(z.unknown()).default({}),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.schemaVersion !== GRAPH_PATH_RESULT_SCHEMA_VERSION) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Unsupported graph path result schema version: ${String(value.schemaVersion)}`,
      });
    }
  });

export type GraphNodeV1 = z.infer<typeof graphNodeSchema>;
export type GraphEdgeV1 = z.infer<typeof graphEdgeSchema>;
export type GraphClusterV1 = z.infer<typeof graphClusterSchema>;
export type GraphSnapshotV1 = z.infer<typeof graphSnapshotSchema>;
export type GraphDeltaV1 = z.infer<typeof graphDeltaSchema>;
export type GraphPathQueryV1 = z.infer<typeof graphPathQuerySchema>;
export type GraphPathResultV1 = z.infer<typeof graphPathResultSchema>;
