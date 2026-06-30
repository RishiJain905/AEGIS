import {
  LayoutWorkerResultStatus,
  parseLayoutWorkerResult,
  type LayoutWorkerCancelMessage,
  type LayoutWorkerRequest,
  type LayoutWorkerResult,
  type LayoutWorkerShutdownMessage,
} from '../contracts/layout-worker-protocol';

export type LayoutWorkerMessageHandler = (result: LayoutWorkerResult) => void;

export class LayoutWorkerClient {
  private worker: Worker | null = null;
  private ready = false;
  private messageHandler: LayoutWorkerMessageHandler | null = null;

  constructor(private readonly createWorker: () => Worker = defaultCreateWorker) {}

  async initialize(onMessage: LayoutWorkerMessageHandler): Promise<void> {
    this.messageHandler = onMessage;
    if (this.worker) {
      return;
    }

    this.worker = this.createWorker();
    this.worker.addEventListener('message', this.handleMessage);

    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Layout worker failed to initialize'));
      }, 5000);

      const onReady = (event: MessageEvent<unknown>) => {
        if (event.data && typeof event.data === 'object' && 'type' in event.data) {
          const payload = event.data as { type?: string };
          if (payload.type === 'ready') {
            clearTimeout(timeout);
            this.worker?.removeEventListener('message', onReady);
            this.ready = true;
            resolve();
          }
        }
      };

      this.worker?.addEventListener('message', onReady);
    });
  }

  private handleMessage = (event: MessageEvent<unknown>): void => {
    if (event.data && typeof event.data === 'object' && 'type' in event.data) {
      return;
    }

    try {
      const result = parseLayoutWorkerResult(event.data);
      this.messageHandler?.(result);
    } catch {
      // Ignore malformed worker messages.
    }
  };

  runLayout(request: LayoutWorkerRequest): void {
    if (!this.worker || !this.ready) {
      throw new Error('Layout worker is not ready');
    }
    this.worker.postMessage(request);
  }

  cancel(requestId: string): void {
    if (!this.worker) {
      return;
    }
    const message: LayoutWorkerCancelMessage = { type: 'cancel', requestId };
    this.worker.postMessage(message);
  }

  shutdown(): void {
    if (!this.worker) {
      return;
    }

    const message: LayoutWorkerShutdownMessage = { type: 'shutdown' };
    this.worker.postMessage(message);
    this.worker.removeEventListener('message', this.handleMessage);
    this.worker.terminate();
    this.worker = null;
    this.ready = false;
    this.messageHandler = null;
  }

  isResultTerminal(status: LayoutWorkerResult['status']): boolean {
    return (
      status === LayoutWorkerResultStatus.COMPLETE ||
      status === LayoutWorkerResultStatus.CANCELLED ||
      status === LayoutWorkerResultStatus.ERROR
    );
  }
}

function defaultCreateWorker(): Worker {
  return new Worker(new URL('../../../workers/layout/layout.worker.ts', import.meta.url), {
    type: 'module',
  });
}
