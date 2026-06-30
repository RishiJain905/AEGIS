import { test, expect } from '@playwright/test';

const DEFAULT_RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

test.describe('graph domain harness', () => {
  test('shows sigma operational graph on active run', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('visualization-slot')).toBeVisible();
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible();
    await expect(page.getByTestId('graph-domain-harness')).not.toBeVisible();
  });

  test('shows operational graph description instead of placeholder', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByText('Graph visualization placeholder')).not.toBeVisible();
    await expect(page.getByText('Sigma.js operational investigation graph')).toBeVisible();
  });
});
