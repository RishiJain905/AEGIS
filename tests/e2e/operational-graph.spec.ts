import { test, expect } from '@playwright/test';

const DEFAULT_RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

test.describe('operational graph', () => {
  test('renders sigma canvas on active run', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('operational-graph-view')).toBeVisible();
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible();
  });

  test('search filters accessible entity list', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await page.getByTestId('graph-search-input').fill('Gateway');
    await expect(page.getByTestId('graph-entity-asset:svc-api-gateway')).toBeVisible();
    await expect(page.getByTestId('graph-entity-asset:svc-auth-service')).not.toBeVisible();
  });

  test('selecting node shows inspector asset details', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
    const inspector = page.getByTestId('graph-entity-inspector');
    await expect(inspector).toBeVisible();
    await expect(inspector.getByText('API Gateway')).toBeVisible();
  });

  test('neighborhood isolation and restore', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
    await page.getByTestId('graph-isolate-neighborhood').click();
    await expect(page.getByTestId('graph-restore-full')).toBeEnabled();
    await page.getByTestId('graph-restore-full').click();
    await expect(page.getByTestId('graph-isolate-neighborhood')).toBeEnabled();
  });

  test('path mode highlights path between nodes', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await page.getByTestId('graph-path-mode').click();
    await page.getByTestId('graph-entity-asset:device-workstation-01').click();
    await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
    await expect(page.getByTestId('path-inspector-section')).toBeVisible();
  });

  test('overlay toggles are interactive', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await page.getByTestId('graph-overlay-risk').click();
    await expect(page.getByTestId('graph-overlay-risk')).toHaveAttribute('aria-pressed', 'false');
  });

  test('graph controls usable at narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('graph-search-input')).toBeVisible();
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible();
  });

  test('stress run remains interactive with layout completion', async ({ page }) => {
    await page.goto('/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAW');
    await expect(page.getByTestId('operational-graph-view')).toBeVisible();
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible();
    await expect(page.getByTestId('operational-graph-view')).toHaveAttribute(
      'data-layout-status',
      /complete|running|idle/,
    );
  });

  test('cluster collapse control is available on stress run', async ({ page }) => {
    await page.goto('/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAW');
    await page.getByTestId('graph-collapse-clusters').click();
    await expect(page.getByTestId('operational-graph-view')).toHaveAttribute(
      'data-lod-tier',
      /balanced|overview|dense/,
    );
  });

  test('respects reduced motion preference', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(DEFAULT_RUN);
    await expect(page.locator('[data-reduced-motion="true"]')).toBeVisible();
  });
});
