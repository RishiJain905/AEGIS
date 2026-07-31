import { ApiClientError } from '@/lib/api/types';

/**
 * What the operator is told when a queue read fails. "Something went wrong" plus a
 * Retry button is the same answer for an expired session, a stopped API, and a
 * malformed payload — three problems with three different remedies. Classifying the
 * failure lets the surface name the remedy, and lets it hide Retry where retrying
 * cannot help.
 */
export type QueueFailureKind = 'auth' | 'permission' | 'connectivity' | 'throttled' | 'data';

export interface QueueFailure {
  kind: QueueFailureKind;
  title: string;
  message: string;
  /** False when re-issuing the same request cannot plausibly succeed. */
  retryable: boolean;
}

export function describeQueueFailure(error: unknown): QueueFailure {
  if (error instanceof ApiClientError) {
    if (error.status === 401) {
      return {
        kind: 'auth',
        title: 'Your session has expired',
        message: 'Sign in again to read the incident queue.',
        retryable: false,
      };
    }
    if (error.status === 403) {
      return {
        kind: 'permission',
        title: 'Not authorised to read incidents',
        message: 'Your role does not grant access to this run’s incidents.',
        retryable: false,
      };
    }
    if (error.status === 429) {
      return {
        kind: 'throttled',
        title: 'Too many requests',
        message: 'The API is rate-limiting this session. Wait a moment, then retry.',
        retryable: true,
      };
    }
    if (error.status >= 500) {
      return {
        kind: 'connectivity',
        title: 'The API could not serve the queue',
        message: `The incidents service returned an error (${String(error.status)}). Retry, or check that the API is healthy.`,
        retryable: true,
      };
    }
    return {
      kind: 'data',
      title: 'The incident queue could not be read',
      message: error.message,
      retryable: true,
    };
  }

  // A raw fetch rejection: the API is unreachable, blocked by CORS, or the request
  // was aborted before a response existed. There is no status to report.
  if (error instanceof TypeError) {
    return {
      kind: 'connectivity',
      title: 'Cannot reach the API',
      message: 'The incidents service did not respond. Check that the API is running, then retry.',
      retryable: true,
    };
  }

  return {
    kind: 'data',
    title: 'The incident queue could not be read',
    message: error instanceof Error ? error.message : 'An unexpected error occurred.',
    retryable: true,
  };
}
