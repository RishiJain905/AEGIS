import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

import { expect, test } from '@playwright/test';

import {
  defaultGraphBenchmarkManifest,
  getBenchmarkDataset,
} from '../../../apps/web/features/operational-graph/contracts/benchmark-manifest';
import { PerformanceInstrumentation } from '../../../apps/web/features/operational-graph/performance/performance-instrumentation';

const TARGET_RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FBY';
const STRESS_RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAW';
const DEFAULT_RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const TARGET_LAYOUT_BUDGET = { p50Ms: 8000, p95Ms: 8000, p99Ms: 8000 };
const STRESS_LAYOUT_BUDGET = { p50Ms: 20000, p95Ms: 20000, p99Ms: 20000 };

const MOCK_AUTH_SESSION = {
  schemaVersion: 1,
  authenticated: true,
  actor: {
    schemaVersion: 1,
    userId: 'user:operator-alpha',
    displayName: 'Operator Alpha',
    roles: ['operator'],
    permissions: [
      'runs:read',
      'runs:write',
      'investigation:read',
      'investigation:trigger',
      'approvals:decide',
      'replay:read',
      'replay:write',
      'reports:read',
      'reports:export',
      'reports:trigger',
      'scoring:read',
      'scoring:compute',
      'scoring:export',
      'ws:subscribe',
    ],
    sessionId: 'sess_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    authMethod: 'dev',
  },
  session: {
    schemaVersion: 1,
    sessionId: 'sess_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    userId: 'user:operator-alpha',
    authMethod: 'dev',
    createdAt: '2026-01-01T00:00:00Z',
    expiresAt: '2026-01-01T08:00:00Z',
    revokedAt: null,
    csrfToken: 'csrf_01ARZ3NDEKTSV4RRFFQ69G5FAVxx',
  },
};

type BrowserMetric = {
  metric: string;
  sampleCount: number;
  p50Ms: number;
  p95Ms: number;
  p99Ms: number;
  budgetMs: { p50Ms: number; p95Ms: number; p99Ms: number };
  status: 'passed' | 'failed';
  visibleNodes?: number;
  visibleEdges?: number;
};

function oneSampleMetric(
  metric: string,
  elapsedMs: number,
  budgetMs: { p50Ms: number; p95Ms: number; p99Ms: number },
  visibleNodes: number,
  visibleEdges: number,
): BrowserMetric {
  return {
    metric,
    sampleCount: 1,
    p50Ms: Number(elapsedMs.toFixed(3)),
    p95Ms: Number(elapsedMs.toFixed(3)),
    p99Ms: Number(elapsedMs.toFixed(3)),
    budgetMs,
    status:
      elapsedMs <= budgetMs.p50Ms && elapsedMs <= budgetMs.p95Ms && elapsedMs <= budgetMs.p99Ms
        ? 'passed'
        : 'failed',
    visibleNodes,
    visibleEdges,
  };
}

function reportPath(): string {
  return resolve(
    process.env.AEGIS_RELEASE_BROWSER_PERFORMANCE_REPORT_PATH ??
      '../../docs/release/evidence/browser-performance.json',
  );
}

test.describe('Phase 34 graph/browser performance capability', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/session', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_AUTH_SESSION),
      });
    });
  });

  test('measures benchmark target/stress layout and 3D capability', async ({ page }) => {
    test.setTimeout(120_000);
    const metrics: BrowserMetric[] = [];
    const skips: Array<{ metric: string; reason: string }> = [];
    const instrumentation = new PerformanceInstrumentation();
    const target = getBenchmarkDataset(defaultGraphBenchmarkManifest, 'target');
    const stress = getBenchmarkDataset(defaultGraphBenchmarkManifest, 'stress');

    async function measure2d(runId: string, dataset: typeof target, metric: string): Promise<void> {
      await page.goto(`/runs/${runId}`);
      await expect(page.getByTestId('operational-graph-view')).toBeVisible();
      await expect(page.getByTestId('operational-graph-canvas')).toBeVisible();
      const started = performance.now();
      const layoutBudget =
        metric === 'graph.2d.target_layout' ? TARGET_LAYOUT_BUDGET : STRESS_LAYOUT_BUDGET;
      await expect(page.getByTestId('operational-graph-view')).toHaveAttribute(
        'data-layout-status',
        'complete',
        {
          timeout: Number(process.env.AEGIS_BROWSER_LAYOUT_TIMEOUT_MS ?? layoutBudget.p99Ms),
        },
      );
      const elapsedMs = performance.now() - started;
      const graphView = page.getByTestId('operational-graph-view');
      await expect(graphView).toHaveAttribute('data-node-count', String(dataset.nodeCount));
      const visibleNodes = dataset.nodeCount;
      instrumentation.recordSample({
        frameTimeMs: elapsedMs,
        syncLatencyMs: elapsedMs,
        workerDurationMs: null,
        visibleNodes,
        visibleEdges: dataset.edgeCount,
        lodTier:
          (await page.getByTestId('operational-graph-view').getAttribute('data-lod-tier')) ??
          'unknown',
        droppedFrames: 0,
        droppedWorkerResults: 0,
      });
      metrics.push(
        oneSampleMetric(metric, elapsedMs, layoutBudget, visibleNodes, dataset.edgeCount),
      );
    }

    await measure2d(TARGET_RUN, target, 'graph.2d.target_layout');
    await measure2d(STRESS_RUN, stress, 'graph.2d.stress_layout');

    await page.goto(`/runs/${DEFAULT_RUN}`);
    const started3d = performance.now();
    await page.getByTestId('graph-view-mode-3d').click();
    const threeD = page.getByTestId('cinematic-graph-view');
    const fallback = page.getByTestId('cinematic-capability-fallback');
    await expect(threeD.or(fallback)).toBeVisible({ timeout: 12_000 });
    if (await fallback.isVisible()) {
      skips.push({
        metric: 'graph.3d.mount_to_visible',
        reason: 'WebGL capability probe selected the supported 2D fallback',
      });
    } else {
      const canvas = page.getByTestId('cinematic-graph-canvas').locator('canvas');
      await expect(canvas).toBeVisible({ timeout: 12_000 });
      const elapsed3d = performance.now() - started3d;
      expect(elapsed3d).toBeLessThanOrEqual(10_000);
      metrics.push(
        oneSampleMetric(
          'graph.3d.mount_to_visible',
          elapsed3d,
          { p50Ms: 8000, p95Ms: 8000, p99Ms: 10000 },
          12,
          19,
        ),
      );
    }

    const output = {
      schemaVersion: 'aegis.release-browser-performance/v1',
      browser: test.info().project.name,
      capability: await page.evaluate(() => ({
        webgl: Boolean(document.querySelector('[data-testid="cinematic-graph-canvas"] canvas')),
      })),
      metrics,
      skips,
      samples: instrumentation.getSamples(),
      status: metrics.every((metric) => metric.status === 'passed') ? 'passed' : 'failed',
    };
    const path = reportPath();
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, `${JSON.stringify(output, null, 2)}\n`, 'utf8');
    expect(output.status).toBe('passed');
  });
});
