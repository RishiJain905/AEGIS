import { test, expect } from '@playwright/test';

const DEFAULT_RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const INCIDENT_PATH = `/incidents/${encodeURIComponent('incident:inc_synthetic_001')}`;

test.describe('application shell', () => {
  test('navigates primary command-centre regions on desktop', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('command-centre-shell')).toBeVisible();
    await expect(page.getByTestId('operations-rail')).toBeVisible();
    await expect(page.getByTestId('status-strip')).toBeVisible();
    await expect(page.getByTestId('visualization-slot')).toBeVisible();
    await expect(page.getByTestId('inspector-panel')).toBeVisible();
    await expect(page.getByTestId('timeline-area')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Operational graph' })).toBeVisible();
  });

  test('navigates all product areas through the operations rail', async ({ page }) => {
    await page.goto('/scenarios');
    await expect(page.getByRole('heading', { name: 'Scenario selection' })).toBeVisible();

    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('visualization-slot')).toBeVisible();

    await page.goto(INCIDENT_PATH);
    await expect(page.getByTestId('inspector-panel')).toBeVisible();

    await page.goto('/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV');
    await expect(page.getByRole('region', { name: 'Replay workspace' })).toBeVisible();

    await page.goto('/reports');
    await expect(page.getByRole('region', { name: 'Reports' })).toBeVisible();

    await page.goto('/admin');
    await expect(page.getByRole('region', { name: 'Administration' })).toBeVisible();
  });

  test('opens command palette with keyboard shortcut', async ({ page }) => {
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('command-centre-shell')).toBeVisible();
    await page.locator('body').click();
    await page.keyboard.press('Control+k');
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByTestId('command-palette-input')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('shows empty scenarios state via fixture profile', async ({ page }) => {
    await page.goto('/scenarios?profile=empty');
    await expect(page.getByTestId('scenarios-empty')).toBeVisible();
  });

  test('shows offline connection banner via fixture profile', async ({ page }) => {
    await page.goto(`${DEFAULT_RUN}?profile=offline`);
    await expect(page.getByTestId('connection-banner')).toBeVisible();
    await expect(
      page.getByTestId('status-strip').getByText('Offline', { exact: true }),
    ).toBeVisible();
  });

  test('shows partial graph state via fixture profile', async ({ page }) => {
    await page.goto(`${DEFAULT_RUN}?profile=partial`);
    await expect(page.getByTestId('partial-graph-alert')).toBeVisible();
    await expect(page.getByText('Graph unavailable')).toBeVisible();
  });

  test('renders narrower responsive layout with mobile menu', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto(DEFAULT_RUN);
    await expect(page.getByTestId('open-mobile-rail')).toBeVisible();
    await page.getByTestId('open-mobile-rail').click();
    await expect(
      page.getByRole('navigation', { name: 'Mobile operations navigation' }),
    ).toBeVisible();
  });

  test('returns not found for invalid run id', async ({ page }) => {
    await page.goto('/runs/run_does_not_exist');
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  });
});
