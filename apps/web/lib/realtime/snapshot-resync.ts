import type { SnapshotBootstrapPayloadV1 } from '@aegis/contracts-ts';
import {
  graphSnapshotSchema,
  parseContract,
  runSchema,
  snapshotBootstrapPayloadSchema,
} from '@aegis/contracts-ts';

import { apiFetch } from '@/lib/api/auth-fetch';

export async function fetchSnapshotBootstrap(
  runId: string,
  signal?: AbortSignal,
): Promise<SnapshotBootstrapPayloadV1> {
  const response = await apiFetch(`/api/v1/runs/${runId}/bootstrap`, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch bootstrap payload: ${String(response.status)}`);
  }
  const body: unknown = await response.json();
  return parseContract(snapshotBootstrapPayloadSchema, body);
}

export async function fetchRunGraphSnapshot(runId: string, signal?: AbortSignal) {
  const response = await apiFetch(`/api/v1/runs/${runId}/graph`, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch graph snapshot: ${String(response.status)}`);
  }
  const body: unknown = await response.json();
  return parseContract(graphSnapshotSchema, body);
}

export async function fetchRunRecord(runId: string, signal?: AbortSignal) {
  const response = await apiFetch(`/api/v1/runs/${runId}`, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch run record: ${String(response.status)}`);
  }
  const body: unknown = await response.json();
  return parseContract(runSchema, body);
}

export async function buildBootstrapFromEndpoints(
  runId: string,
  signal?: AbortSignal,
): Promise<SnapshotBootstrapPayloadV1> {
  try {
    return await fetchSnapshotBootstrap(runId, signal);
  } catch {
    const [run, graphSnapshot] = await Promise.all([
      fetchRunRecord(runId, signal),
      fetchRunGraphSnapshot(runId, signal),
    ]);
    return {
      schemaVersion: 1,
      run,
      graphSnapshot,
      lastAppliedSequence: graphSnapshot.sequence,
    };
  }
}
