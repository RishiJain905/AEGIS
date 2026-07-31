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
    // The asset's composed operator-facing status: a containing control reads
    // 'contained', otherwise the security posture underneath shows through.
    status: z.enum(['normal', 'suspicious', 'under_investigation', 'contained', 'compromised']),
    revision: revisionSchema,
    // Defensive controls currently applied, in application order ('observed',
    // 'isolated', ...). Additive (schemaVersion stays 1) and optional, so legacy payloads
    // and fixtures are unaffected. Carried beside `status` rather than folded into it:
    // the two answer different questions — what is wrong with this asset, and what have
    // we done about it — and folding them lost the first one.
    appliedControls: z.array(z.string()).optional(),
    // Fog of war: whether the operator may see this node's true security state yet.
    // Additive (schemaVersion stays 1); optional so existing producers/fixtures are
    // unaffected — the server always sends it and consumers treat an absent value as
    // disclosed. Undisclosed nodes arrive with a redacted (baseline) status until detected.
    disclosed: z.boolean().optional(),
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

export type NodeStatusV1 = GraphNodeV1['status'];

/**
 * World-state asset status -> the operator-facing `NodeStatus` it projects to. Mirror of
 * `aegis_contracts.killchain.NODE_STATUS_BY_WORLD_STATUS`; keep the two in step.
 *
 * `sim.asset.status_changed` carries the *world* status, which for a containment effect
 * is the richer response-toolkit vocabulary ("isolated", "credentials_revoked", ...)
 * rather than a `NodeStatus`. Anything rendering a node off that payload has to translate
 * first, or it hands the graph a status no status-presentation table knows.
 */
export const NODE_STATUS_BY_WORLD_STATUS: Record<string, NodeStatusV1> = {
  observed: NodeStatus.UNDER_INVESTIGATION,
  heightened_monitoring: NodeStatus.UNDER_INVESTIGATION,
  isolated: NodeStatus.CONTAINED,
  access_restricted: NodeStatus.CONTAINED,
  credentials_revoked: NodeStatus.CONTAINED,
  restarting: NodeStatus.CONTAINED,
  rolling_back: NodeStatus.CONTAINED,
  contained: NodeStatus.CONTAINED,
  quarantined: NodeStatus.CONTAINED,
};

const NODE_STATUS_VALUES = new Set<string>(Object.values(NodeStatus));

/**
 * Project a world-state asset status onto the graph vocabulary. Values that are already a
 * `NodeStatus` pass through; containment statuses map through
 * {@link NODE_STATUS_BY_WORLD_STATUS}; anything unrecognized falls back to
 * `under_investigation` (something moved this asset off baseline, and rendering an
 * unknown status is worse than rendering an imprecise one).
 */
export function projectNodeStatus(worldStatus: string): NodeStatusV1 {
  if (NODE_STATUS_VALUES.has(worldStatus)) {
    return worldStatus as NodeStatusV1;
  }
  return NODE_STATUS_BY_WORLD_STATUS[worldStatus] ?? NodeStatus.UNDER_INVESTIGATION;
}

/** Every value the defensive-control vocabulary can take. */
export const CONTROL_STATUSES: ReadonlySet<string> = new Set(
  Object.keys(NODE_STATUS_BY_WORLD_STATUS),
);

/**
 * Controls that take the asset away from the attacker — an asset carrying one of these
 * reads as `contained` however the attacker had left it.
 */
export const CONTAINING_CONTROL_STATUSES: ReadonlySet<string> = new Set(
  Object.entries(NODE_STATUS_BY_WORLD_STATUS)
    .filter(([, projected]) => projected === NodeStatus.CONTAINED)
    .map(([status]) => status),
);

/**
 * Controls that only change what the defender is watching. These never mask the posture
 * underneath — an observed compromise is still a compromise.
 */
export const OBSERVATION_CONTROL_STATUSES: ReadonlySet<string> = new Set(
  Object.entries(NODE_STATUS_BY_WORLD_STATUS)
    .filter(([, projected]) => projected === NodeStatus.UNDER_INVESTIGATION)
    .map(([status]) => status),
);

/**
 * Whether a status names a defensive control rather than a security posture. The two
 * vocabularies overlap on exactly one value, `contained`, which counts as a control: it
 * is what a defender action does to an asset.
 */
export function isControlStatus(status: string): boolean {
  return CONTROL_STATUSES.has(status);
}

/**
 * Compose a security posture and its applied controls into one node status. Mirror of
 * `aegis_contracts.killchain.project_effective_status`; keep the two in step.
 *
 * A containing control wins (isolating a compromised host reads `contained` — the
 * response is the salient fact, and the world still remembers the compromise). Otherwise
 * a non-baseline posture wins, so observing a compromised host leaves it reading
 * `compromised` instead of hiding the intrusion behind the act of watching it. An
 * observation control on an otherwise-clean asset reads `under_investigation`.
 */
export function projectEffectiveStatus(
  posture: string,
  appliedControls: readonly string[] = [],
): NodeStatusV1 {
  if (appliedControls.some((control) => CONTAINING_CONTROL_STATUSES.has(control))) {
    return NodeStatus.CONTAINED;
  }
  const postureStatus = projectNodeStatus(posture);
  if (postureStatus !== NodeStatus.NORMAL) {
    return postureStatus;
  }
  if (appliedControls.some((control) => OBSERVATION_CONTROL_STATUSES.has(control))) {
    return NodeStatus.UNDER_INVESTIGATION;
  }
  return NodeStatus.NORMAL;
}
