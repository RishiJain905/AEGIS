import { test, expect } from '@playwright/test';

const DEFAULT_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

test.describe('Live run command centre', () => {
  test('fixture mode preserves operational graph and timeline', async ({ page }) => {
    await page.goto(`/runs/${DEFAULT_RUN_ID}`);
    await expect(page.getByTestId('command-centre-shell')).toBeVisible();
    await expect(page.getByTestId('timeline-area')).toBeVisible();
    await expect(page.getByTestId('status-strip')).toBeVisible();
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible({
      timeout: 30_000,
    });
  });

  test('responsive layout keeps timeline usable', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto(`/runs/${DEFAULT_RUN_ID}`);
    await expect(page.getByTestId('timeline-area')).toBeVisible();
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible({
      timeout: 30_000,
    });
  });
});
