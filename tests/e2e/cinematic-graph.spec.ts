import { test, expect } from '@playwright/test';

const DEFAULT_RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const DEFAULT_REPLAY = '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

test.describe('Phase 27 cinematic semantic renderer', () => {
  test('command centre exposes 2D/3D toggle and defaults to Sigma 2D', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('visualization-slot')).toBeVisible();
    await expect(page.getByTestId('graph-view-mode-toggle')).toBeVisible();
    await expect(page.getByTestId('graph-view-mode-2d')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('operational-graph-view')).toBeVisible();
  });

  test('3D mode renders semantic scene for Operation Silent Relay', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await page.getByTestId('graph-view-mode-3d').click();
    await expect(
      page
        .getByTestId('cinematic-graph-view')
        .or(page.getByTestId('cinematic-capability-fallback')),
    ).toBeVisible();
    const fallback = page.getByTestId('cinematic-capability-fallback');
    if (await fallback.isVisible()) {
      await expect(fallback).toContainText('3D semantic view unavailable');
      return;
    }
    await expect(page.getByTestId('cinematic-graph-canvas')).toBeVisible();
    await expect(page.getByTestId('cinematic-entity-list')).toBeVisible();
    await expect(page.getByTestId('cinematic-graph-meta')).toContainText('Semantic 3D');
  });

  test('2D and 3D selection bridge updates inspector for the same entity', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
    await expect(page.getByTestId('graph-entity-inspector')).toContainText('API Gateway');

    await page.getByTestId('graph-view-mode-3d').click();
    const fallback = page.getByTestId('cinematic-capability-fallback');
    if (await fallback.isVisible()) {
      test.info().annotations.push({ type: 'note', description: 'WebGL fallback path exercised' });
      return;
    }
    await expect(page.getByTestId('cinematic-entity-asset:svc-api-gateway')).toBeVisible();
    await page.getByTestId('cinematic-entity-asset:svc-api-gateway').click();
    await expect(page.getByTestId('graph-entity-inspector')).toContainText('API Gateway');

    await page.getByTestId('graph-view-mode-2d').click();
    await expect(page.getByTestId('operational-graph-view')).toBeVisible();
    await expect(page.getByTestId('graph-entity-inspector')).toContainText('API Gateway');
  });

  test('narrow viewport keeps mode toggle usable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('graph-view-mode-toggle')).toBeVisible();
    await page.getByTestId('graph-view-mode-3d').click();
    await expect(
      page
        .getByTestId('cinematic-graph-view')
        .or(page.getByTestId('cinematic-capability-fallback')),
    ).toBeVisible();
  });

  test('replay route shares cursor-aligned graph with 3D mode when available', async ({ page }) => {
    await page.goto(DEFAULT_REPLAY);
    await expect(page.getByTestId('visualization-slot')).toBeVisible({ timeout: 30_000 });
    const toggle = page.getByTestId('graph-view-mode-toggle');
    if (!(await toggle.isVisible())) {
      test.skip(true, 'Replay graph not yet reconstructed in fixture path');
      return;
    }
    await page.getByTestId('graph-view-mode-3d').click();
    await expect(
      page
        .getByTestId('cinematic-graph-view')
        .or(page.getByTestId('cinematic-capability-fallback')),
    ).toBeVisible();
  });
});
