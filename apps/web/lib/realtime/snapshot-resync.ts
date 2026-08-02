import type { SnapshotBootstrapPayloadV1 } from '@aegis/contracts-ts';
import {
  ContractValidationError,
  graphSnapshotSchema,
  parseContract,
  runSchema,
  snapshotBootstrapPayloadSchema,
} from '@aegis/contracts-ts';

import { apiFetch } from '@/lib/api/auth-fetch';
import { ApiClientError } from '@/lib/api/types';

async function fetchParsed<T>(
  path: string,
  what: string,
  parse: (data: unknown) => T,
  signal?: AbortSignal,
): Promise<T> {
  const response = await apiFetch(path, { signal });
  if (!response.ok) {
    // Carries the status so callers can tell "this endpoint is not there" from "the
    // server is shedding load". Throwing a bare Error here erased that distinction, and
    // `buildBootstrapFromEndpoints` below turned every failure — including a 429 — into
    // two further requests.
    throw new ApiClientError({
      code: 'HTTP_ERROR',
      message: `Failed to fetch ${what}: ${String(response.status)}`,
      status: response.status,
    });
  }
  const body: unknown = await response.json();
  return parse(body);
}

export async function fetchSnapshotBootstrap(
  runId: string,
  signal?: AbortSignal,
): Promise<SnapshotBootstrapPayloadV1> {
  return fetchParsed(
    `/api/v1/runs/${runId}/bootstrap`,
    'bootstrap payload',
    (body) => parseContract(snapshotBootstrapPayloadSchema, body),
    signal,
  );
}

export async function fetchRunGraphSnapshot(runId: string, signal?: AbortSignal) {
  return fetchParsed(
    `/api/v1/runs/${runId}/graph`,
    'graph snapshot',
    (body) => parseContract(graphSnapshotSchema, body),
    signal,
  );
}

export async function fetchRunRecord(runId: string, signal?: AbortSignal) {
  return fetchParsed(
    `/api/v1/runs/${runId}`,
    'run record',
    (body) => parseContract(runSchema, body),
    signal,
  );
}

/**
 * Statuses that mean the composite endpoint cannot serve this client at all — it is absent,
 * or the method is not implemented. Asking again changes nothing, so assembling the payload
 * from the per-resource endpoints is the only way forward.
 */
const BOOTSTRAP_UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

/**
 * Whether a failed `/bootstrap` should be retried as the two-endpoint pair.
 *
 * Only when the composite endpoint is structurally unable to answer: it is missing, or it
 * answered with a body this client's schema rejects (in which case the narrower per-resource
 * schemas may still parse). A 429, a 5xx, a timeout or a dropped connection are all
 * *load or transient* signals, and fanning a single failure out into two more requests is
 * the exact opposite of what they ask for — QA watched a failing bootstrap turn into 43
 * back-to-back `/runs/{id}` + `/runs/{id}/graph` pairs, every one of them rate-limited.
 */
function shouldFallBackToEndpointPair(error: unknown): boolean {
  if (error instanceof ContractValidationError) {
    return true;
  }
  if (error instanceof ApiClientError) {
    return BOOTSTRAP_UNAVAILABLE_STATUSES.has(error.status);
  }
  return false;
}

export async function buildBootstrapFromEndpoints(
  runId: string,
  signal?: AbortSignal,
): Promise<SnapshotBootstrapPayloadV1> {
  try {
    return await fetchSnapshotBootstrap(runId, signal);
  } catch (error) {
    if (!shouldFallBackToEndpointPair(error)) {
      throw error;
    }
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
