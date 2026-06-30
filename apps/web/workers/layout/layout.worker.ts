import {
  LayoutWorkerErrorCode,
  LayoutWorkerResultStatus,
  parseLayoutWorkerInboundMessage,
  parseLayoutWorkerRequest,
} from '@/features/operational-graph/contracts/layout-worker-protocol';

import { createCancelledResult, createCompleteResult, runForceAtlas2 } from './force-atlas2-runner';

let activeRequestId: string | null = null;
let cancelRequested = false;

function postResult(result: unknown): void {
  self.postMessage(result);
}

self.addEventListener('message', (event: MessageEvent<unknown>) => {
  try {
    const message = parseLayoutWorkerInboundMessage(event.data);

    if ('type' in message) {
      if (message.type === 'shutdown') {
        activeRequestId = null;
        cancelRequested = false;
        self.close();
      }
      if (message.type === 'cancel') {
        if (activeRequestId === message.requestId) {
          cancelRequested = true;
        }
      }
      return;
    }

    const request = parseLayoutWorkerRequest(message);
    activeRequestId = request.requestId;
    cancelRequested = false;
    const startedAt = performance.now();
    const cancellation = { requested: false };

    const { positions, iterationsCompleted } = runForceAtlas2(
      request,
      () => {
        if (cancelRequested && activeRequestId === request.requestId) {
          cancellation.requested = true;
          return true;
        }
        return false;
      },
      (completed) => {
        postResult({
          protocolVersion: 1,
          requestId: request.requestId,
          graphRevision: request.graphRevision,
          status: LayoutWorkerResultStatus.PROGRESS,
          iterationsCompleted: completed,
          durationMs: performance.now() - startedAt,
        });
      },
    );

    const durationMs = performance.now() - startedAt;

    if (cancellation.requested) {
      postResult(createCancelledResult(request, iterationsCompleted, durationMs));
      activeRequestId = null;
      cancelRequested = false;
      return;
    }

    postResult(createCompleteResult(request, positions, iterationsCompleted, durationMs));
    activeRequestId = null;
  } catch (error) {
    postResult({
      protocolVersion: 1,
      requestId: 'unknown',
      graphRevision: {
        schemaVersion: 1,
        runId: 'unknown',
        sequence: 0,
        revision: 0,
      },
      status: LayoutWorkerResultStatus.ERROR,
      iterationsCompleted: 0,
      durationMs: 0,
      errorCode: LayoutWorkerErrorCode.INTERNAL,
      errorMessage: error instanceof Error ? error.message : 'Unknown worker error',
    });
  }
});

postResult({ type: 'ready' });
