import { test, expect } from '@playwright/test';

const DEFAULT_RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

test.describe('graph domain harness', () => {
  test('shows phase 05 domain engine metrics on active run', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('visualization-slot')).toBeVisible();
    await expect(page.getByTestId('graph-domain-harness')).toBeVisible();
    await expect(page.getByTestId('graph-domain-delta-status')).toContainText('duplicate');
    await expect(page.getByTestId('graph-domain-path')).toBeVisible();
  });

  test('keeps phase 04 visualization placeholder above harness', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByText('Graph visualization placeholder')).toBeVisible();
    await expect(page.getByText('Sigma.js renderer — Phase 06')).toBeVisible();
    await expect(page.getByText('Graph domain engine')).toBeVisible();
  });
});
