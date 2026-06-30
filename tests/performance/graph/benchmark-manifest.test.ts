import { describe, expect, it } from 'vitest';

import {
  defaultGraphBenchmarkManifest,
  getBenchmarkDataset,
} from '@/features/operational-graph/contracts/benchmark-manifest';

describe('graph benchmark manifest', () => {
  it('defines target and stress datasets with budgets', () => {
    const target = getBenchmarkDataset(defaultGraphBenchmarkManifest, 'target');
    const stress = getBenchmarkDataset(defaultGraphBenchmarkManifest, 'stress');

    expect(target.workerLayoutBudgetMs).toBeGreaterThan(0);
    expect(stress.workerLayoutBudgetMs).toBeGreaterThan(target.workerLayoutBudgetMs);
    expect(defaultGraphBenchmarkManifest.datasets).toHaveLength(2);
  });
});
