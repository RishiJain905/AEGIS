const DEFAULT_FRAME_BUDGET_MS = 16;

export interface UpdateBatcherOptions {
  frameBudgetMs?: number;
  onOverBudget?: () => void;
}

export class UpdateBatcher {
  private readonly frameBudgetMs: number;
  private readonly onOverBudget?: () => void;
  private scheduled = false;
  private pendingTask: (() => void) | null = null;
  private rafId: number | null = null;
  private droppedFrames = 0;

  constructor(options: UpdateBatcherOptions = {}) {
    this.frameBudgetMs = options.frameBudgetMs ?? DEFAULT_FRAME_BUDGET_MS;
    this.onOverBudget = options.onOverBudget;
  }

  schedule(task: () => void): void {
    this.pendingTask = task;
    if (this.scheduled) {
      return;
    }
    this.scheduled = true;
    this.rafId = requestAnimationFrame(() => {
      this.scheduled = false;
      this.rafId = null;
      const startedAt = performance.now();
      const currentTask = this.pendingTask;
      this.pendingTask = null;
      currentTask?.();

      const elapsed = performance.now() - startedAt;
      if (elapsed > this.frameBudgetMs) {
        this.droppedFrames += 1;
        this.onOverBudget?.();
      }
    });
  }

  getDroppedFrames(): number {
    return this.droppedFrames;
  }

  dispose(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.scheduled = false;
    this.pendingTask = null;
  }
}
