import { z } from 'zod';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';

export const GRAPH_REVISION_SCHEMA_VERSION = 1 as const;

export const graphRevisionSchema = z
  .object({
    schemaVersion: z.literal(GRAPH_REVISION_SCHEMA_VERSION),
    runId: z.string(),
    sequence: z.number().int().nonnegative(),
    revision: z.number().int().nonnegative(),
  })
  .strict();

export type GraphRevision = z.infer<typeof graphRevisionSchema>;

export function graphRevisionFromSnapshot(snapshot: GraphSnapshotV1): GraphRevision {
  return {
    schemaVersion: GRAPH_REVISION_SCHEMA_VERSION,
    runId: snapshot.runId,
    sequence: snapshot.sequence,
    revision: snapshot.revision,
  };
}

export function graphRevisionKey(revision: GraphRevision): string {
  return `${revision.runId}:${String(revision.sequence)}:${String(revision.revision)}`;
}

export function isSameGraphRevision(a: GraphRevision, b: GraphRevision): boolean {
  return graphRevisionKey(a) === graphRevisionKey(b);
}
