import { z } from 'zod';

export const GRAPH_BENCHMARK_MANIFEST_SCHEMA_VERSION = 1 as const;

export const benchmarkDatasetSchema = z
  .object({
    id: z.string(),
    nodeCount: z.number().int().positive(),
    edgeCount: z.number().int().nonnegative(),
    description: z.string(),
    workerLayoutBudgetMs: z.number().positive(),
    adapterSyncBudgetMs: z.number().positive(),
    interactiveFrameBudgetMs: z.number().positive(),
  })
  .strict();

export type BenchmarkDataset = z.infer<typeof benchmarkDatasetSchema>;

export const graphBenchmarkManifestSchema = z
  .object({
    schemaVersion: z.literal(GRAPH_BENCHMARK_MANIFEST_SCHEMA_VERSION),
    datasets: z.array(benchmarkDatasetSchema).min(1),
  })
  .strict();

export type GraphBenchmarkManifest = z.infer<typeof graphBenchmarkManifestSchema>;

export const defaultGraphBenchmarkManifest: GraphBenchmarkManifest = {
  schemaVersion: GRAPH_BENCHMARK_MANIFEST_SCHEMA_VERSION,
  datasets: [
    {
      id: 'target',
      nodeCount: 500,
      edgeCount: 900,
      description: 'Heterogeneous target graph for interactive layout budgets',
      workerLayoutBudgetMs: 8000,
      adapterSyncBudgetMs: 300,
      interactiveFrameBudgetMs: 16,
    },
    {
      id: 'stress',
      nodeCount: 2500,
      edgeCount: 5000,
      description: 'Stress graph for degradation and worker completion budgets',
      workerLayoutBudgetMs: 15000,
      adapterSyncBudgetMs: 250,
      interactiveFrameBudgetMs: 32,
    },
  ],
};

export function parseGraphBenchmarkManifest(data: unknown): GraphBenchmarkManifest {
  return graphBenchmarkManifestSchema.parse(data);
}

export function getBenchmarkDataset(
  manifest: GraphBenchmarkManifest,
  datasetId: string,
): BenchmarkDataset {
  const dataset = manifest.datasets.find((item) => item.id === datasetId);
  if (!dataset) {
    throw new Error(`Unknown benchmark dataset: ${datasetId}`);
  }
  return dataset;
}
