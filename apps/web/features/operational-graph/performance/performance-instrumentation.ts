import {
  createGraphPerformanceSample,
  type GraphPerformanceSample,
} from '../contracts/graph-performance-sample';

const MAX_SAMPLES = 120;

export class PerformanceInstrumentation {
  private readonly samples: GraphPerformanceSample[] = [];
  private droppedWorkerResults = 0;
  private droppedFrames = 0;

  recordSample(partial: Omit<GraphPerformanceSample, 'schemaVersion' | 'capturedAt'>): void {
    const sample = createGraphPerformanceSample(partial);
    this.samples.push(sample);
    if (this.samples.length > MAX_SAMPLES) {
      this.samples.shift();
    }
  }

  recordDroppedWorkerResult(): void {
    this.droppedWorkerResults += 1;
  }

  recordDroppedFrame(): void {
    this.droppedFrames += 1;
  }

  getSamples(): GraphPerformanceSample[] {
    return [...this.samples];
  }

  getLatestSample(): GraphPerformanceSample | null {
    return this.samples.at(-1) ?? null;
  }

  getDroppedWorkerResults(): number {
    return this.droppedWorkerResults;
  }

  getDroppedFrames(): number {
    return this.droppedFrames;
  }

  reset(): void {
    this.samples.length = 0;
    this.droppedWorkerResults = 0;
    this.droppedFrames = 0;
  }
}
