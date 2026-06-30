import { z } from 'zod';

export const GRAPH_PERFORMANCE_SAMPLE_SCHEMA_VERSION = 1 as const;

export const graphPerformanceSampleSchema = z
  .object({
    schemaVersion: z.literal(GRAPH_PERFORMANCE_SAMPLE_SCHEMA_VERSION),
    capturedAt: z.string(),
    frameTimeMs: z.number().nonnegative(),
    syncLatencyMs: z.number().nonnegative(),
    workerDurationMs: z.number().nonnegative().nullable(),
    visibleNodes: z.number().int().nonnegative(),
    visibleEdges: z.number().int().nonnegative(),
    lodTier: z.string(),
    droppedFrames: z.number().int().nonnegative(),
    droppedWorkerResults: z.number().int().nonnegative(),
    memoryEstimateMb: z.number().nonnegative().optional(),
  })
  .strict();

export type GraphPerformanceSample = z.infer<typeof graphPerformanceSampleSchema>;

export function createGraphPerformanceSample(
  partial: Omit<GraphPerformanceSample, 'schemaVersion' | 'capturedAt'>,
): GraphPerformanceSample {
  return {
    schemaVersion: GRAPH_PERFORMANCE_SAMPLE_SCHEMA_VERSION,
    capturedAt: new Date().toISOString(),
    ...partial,
  };
}

export function parseGraphPerformanceSample(data: unknown): GraphPerformanceSample {
  return graphPerformanceSampleSchema.parse(data);
}
