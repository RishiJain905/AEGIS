export const GraphDomainErrorCode = {
  GRAPH_SEQUENCE_GAP: 'GRAPH_SEQUENCE_GAP',
  GRAPH_STALE_REVISION: 'GRAPH_STALE_REVISION',
  GRAPH_DUPLICATE_DELTA: 'GRAPH_DUPLICATE_DELTA',
  GRAPH_CONSISTENCY_VIOLATION: 'GRAPH_CONSISTENCY_VIOLATION',
  GRAPH_ENTITY_NOT_FOUND: 'GRAPH_ENTITY_NOT_FOUND',
  GRAPH_RUN_MISMATCH: 'GRAPH_RUN_MISMATCH',
  GRAPH_VALIDATION_FAILED: 'GRAPH_VALIDATION_FAILED',
} as const;

export type GraphDomainErrorCodeValue =
  (typeof GraphDomainErrorCode)[keyof typeof GraphDomainErrorCode];

export class GraphDomainError extends Error {
  readonly code: GraphDomainErrorCodeValue;
  readonly details: Record<string, unknown>;
  readonly traceId?: string;

  constructor(options: {
    code: GraphDomainErrorCodeValue;
    message: string;
    details?: Record<string, unknown>;
    traceId?: string;
  }) {
    super(options.message);
    this.name = 'GraphDomainError';
    this.code = options.code;
    this.details = options.details ?? {};
    this.traceId = options.traceId;
  }
}
