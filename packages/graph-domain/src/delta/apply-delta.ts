import type { GraphDeltaV1, GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';
import { graphDeltaSchema } from '@aegis/contracts-ts';
import { parseContract } from '@aegis/contracts-ts';

import {
  EDGE_ATTR_KEY,
  getEdgeCanonical,
  getNodeCanonical,
  NODE_ATTR_KEY,
  type CanonicalGraph,
} from '../adapters/canonical-graphology';
import type { GraphClusterV1 } from '@aegis/contracts-ts';
import { GraphDeltaApplyStatus, type GraphDeltaApplyResult } from '../contracts/types';
import { GraphDomainError, GraphDomainErrorCode } from '../errors/graph-domain-error';

export interface DeltaApplicationContext {
  graph: CanonicalGraph;
  clusters: Map<string, GraphClusterV1>;
  runId: string;
  lastAppliedSequence: number;
  snapshotRevision: number;
  capturedAt: string;
}

function isStaleRevision(storedRevision: number, incomingRevision: number): boolean {
  return incomingRevision < storedRevision;
}

function applyUpsertNode(graph: CanonicalGraph, node: GraphNodeV1): GraphDomainError | null {
  const existing = getNodeCanonical(graph, node.id);
  if (existing !== undefined && isStaleRevision(existing.revision, node.revision)) {
    return new GraphDomainError({
      code: GraphDomainErrorCode.GRAPH_STALE_REVISION,
      message: `Stale node revision for ${node.id}`,
      details: {
        entityId: node.id,
        storedRevision: existing.revision,
        incomingRevision: node.revision,
      },
    });
  }

  if (graph.hasNode(node.id)) {
    graph.setNodeAttribute(node.id, NODE_ATTR_KEY, node);
  } else {
    graph.addNode(node.id, { [NODE_ATTR_KEY]: node });
  }
  return null;
}

function applyUpsertEdge(graph: CanonicalGraph, edge: GraphEdgeV1): GraphDomainError | null {
  if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) {
    return new GraphDomainError({
      code: GraphDomainErrorCode.GRAPH_CONSISTENCY_VIOLATION,
      message: `Edge ${edge.id} references missing node endpoints`,
      details: { edgeId: edge.id, source: edge.source, target: edge.target },
    });
  }

  const existing = getEdgeCanonical(graph, edge.id);
  if (existing !== undefined && isStaleRevision(existing.revision, edge.revision)) {
    return new GraphDomainError({
      code: GraphDomainErrorCode.GRAPH_STALE_REVISION,
      message: `Stale edge revision for ${edge.id}`,
      details: {
        entityId: edge.id,
        storedRevision: existing.revision,
        incomingRevision: edge.revision,
      },
    });
  }

  if (graph.hasEdge(edge.id)) {
    graph.setEdgeAttribute(edge.id, EDGE_ATTR_KEY, edge);
  } else {
    graph.addEdgeWithKey(edge.id, edge.source, edge.target, { [EDGE_ATTR_KEY]: edge });
  }
  return null;
}

function applyDeleteNode(graph: CanonicalGraph, targetId: string): GraphDomainError | null {
  if (!graph.hasNode(targetId)) {
    return null;
  }

  const incidentEdges = graph.edges(targetId);
  for (const edgeId of incidentEdges) {
    graph.dropEdge(edgeId);
  }
  graph.dropNode(targetId);
  return null;
}

function applyDeleteEdge(graph: CanonicalGraph, targetId: string): GraphDomainError | null {
  if (!graph.hasEdge(targetId)) {
    return null;
  }
  graph.dropEdge(targetId);
  return null;
}

function applyUpsertCluster(
  clusters: Map<string, GraphClusterV1>,
  cluster: GraphClusterV1,
): GraphDomainError | null {
  const existing = clusters.get(cluster.id);
  if (existing !== undefined && isStaleRevision(existing.revision, cluster.revision)) {
    return new GraphDomainError({
      code: GraphDomainErrorCode.GRAPH_STALE_REVISION,
      message: `Stale cluster revision for ${cluster.id}`,
      details: {
        entityId: cluster.id,
        storedRevision: existing.revision,
        incomingRevision: cluster.revision,
      },
    });
  }
  clusters.set(cluster.id, cluster);
  return null;
}

function applyOperation(
  ctx: DeltaApplicationContext,
  delta: GraphDeltaV1,
): GraphDomainError | null {
  switch (delta.operation) {
    case 'upsert_node':
      if (delta.node === undefined) {
        return new GraphDomainError({
          code: GraphDomainErrorCode.GRAPH_VALIDATION_FAILED,
          message: 'upsert_node requires node payload',
        });
      }
      return applyUpsertNode(ctx.graph, delta.node);
    case 'upsert_edge':
      if (delta.edge === undefined) {
        return new GraphDomainError({
          code: GraphDomainErrorCode.GRAPH_VALIDATION_FAILED,
          message: 'upsert_edge requires edge payload',
        });
      }
      return applyUpsertEdge(ctx.graph, delta.edge);
    case 'delete_node':
      if (delta.targetId === undefined) {
        return new GraphDomainError({
          code: GraphDomainErrorCode.GRAPH_VALIDATION_FAILED,
          message: 'delete_node requires targetId',
        });
      }
      return applyDeleteNode(ctx.graph, delta.targetId);
    case 'delete_edge':
      if (delta.targetId === undefined) {
        return new GraphDomainError({
          code: GraphDomainErrorCode.GRAPH_VALIDATION_FAILED,
          message: 'delete_edge requires targetId',
        });
      }
      return applyDeleteEdge(ctx.graph, delta.targetId);
    case 'upsert_cluster':
      if (delta.cluster === undefined) {
        return new GraphDomainError({
          code: GraphDomainErrorCode.GRAPH_VALIDATION_FAILED,
          message: 'upsert_cluster requires cluster payload',
        });
      }
      return applyUpsertCluster(ctx.clusters, delta.cluster);
    default: {
      const exhaustive: never = delta.operation;
      return new GraphDomainError({
        code: GraphDomainErrorCode.GRAPH_VALIDATION_FAILED,
        message: `Unknown delta operation: ${String(exhaustive)}`,
      });
    }
  }
}

export function applyDeltaToContext(
  ctx: DeltaApplicationContext,
  rawDelta: GraphDeltaV1,
): GraphDeltaApplyResult {
  const delta = parseContract(graphDeltaSchema, rawDelta);

  if (delta.runId !== ctx.runId) {
    return {
      status: GraphDeltaApplyStatus.REJECTED,
      sequence: delta.sequence,
      revision: delta.revision,
      operation: delta.operation,
      errorCode: GraphDomainErrorCode.GRAPH_RUN_MISMATCH,
      message: `Delta runId ${delta.runId} does not match store runId ${ctx.runId}`,
    };
  }

  if (delta.sequence <= ctx.lastAppliedSequence) {
    return {
      status: GraphDeltaApplyStatus.DUPLICATE,
      sequence: delta.sequence,
      revision: delta.revision,
      operation: delta.operation,
      errorCode: GraphDomainErrorCode.GRAPH_DUPLICATE_DELTA,
      message: `Sequence ${String(delta.sequence)} already applied (last: ${String(ctx.lastAppliedSequence)})`,
    };
  }

  if (delta.sequence > ctx.lastAppliedSequence + 1) {
    return {
      status: GraphDeltaApplyStatus.GAP_DETECTED,
      sequence: delta.sequence,
      revision: delta.revision,
      operation: delta.operation,
      errorCode: GraphDomainErrorCode.GRAPH_SEQUENCE_GAP,
      message: `Sequence gap: expected ${String(ctx.lastAppliedSequence + 1)}, received ${String(delta.sequence)}`,
    };
  }

  const operationError = applyOperation(ctx, delta);
  if (operationError !== null) {
    return {
      status: GraphDeltaApplyStatus.REJECTED,
      sequence: delta.sequence,
      revision: delta.revision,
      operation: delta.operation,
      errorCode: operationError.code,
      message: operationError.message,
    };
  }

  ctx.lastAppliedSequence = delta.sequence;
  ctx.snapshotRevision = delta.revision;

  return {
    status: GraphDeltaApplyStatus.APPLIED,
    sequence: delta.sequence,
    revision: delta.revision,
    operation: delta.operation,
  };
}
