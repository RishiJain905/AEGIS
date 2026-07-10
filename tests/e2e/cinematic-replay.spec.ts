import { expect, test } from '@playwright/test';

const REPLAY_PATH = '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

test.describe('Phase 28 cinematic incident replay', () => {
  test('opens Silent Relay replay and enters cinematic mode with historical labeling', async ({
    page,
  }) => {
    await page.goto(REPLAY_PATH);
    await expect(page.getByTestId('historical-mode-banner')).toBeVisible();
    await expect(page.getByTestId('cinematic-mode-toggle')).toBeVisible();
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(page.getByTestId('cinematic-transport-controls')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('cinematic-historical-label')).toContainText(
      /Historical cinematic/i,
    );
    await expect(page.getByTestId('cinematic-chapter-rail')).toBeVisible();
    await expect(page.getByTestId('cinematic-a11y-fallback')).toBeVisible();
  });

  test('advances beats and keeps timeline cursor synchronized', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(page.getByTestId('cinematic-transport-controls')).toBeVisible({ timeout: 15_000 });
    await page.getByTestId('cinematic-next-beat').click();
    await expect(page.getByTestId('cinematic-beat-label')).toContainText(/seq/i);
    await expect(page.getByTestId('replay-cursor-label')).toContainText(/sequence/i);
    await expect(page.getByTestId('cinematic-sync-label')).toBeVisible();
  });

  test('switches between normal and cinematic without losing cursor', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await page.getByTestId('replay-scrubber').fill('180');
    await expect(page.getByTestId('replay-cursor-label')).toContainText('sequence 180');
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(page.getByTestId('cinematic-transport-controls')).toBeVisible({ timeout: 15_000 });
    await page.getByTestId('cinematic-mode-normal').click();
    await expect(page.getByTestId('cinematic-transport-controls')).toHaveCount(0);
    await expect(page.getByTestId('replay-transport-controls')).toBeVisible();
    await expect(page.getByTestId('cinematic-mode-cursor')).toContainText(/Cursor seq/);
  });

  test('open in 2D analysis jumps to beat sequence', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(page.getByTestId('cinematic-open-2d')).toBeVisible({ timeout: 15_000 });
    await page.getByTestId('cinematic-next-beat').click();
    await page.getByTestId('cinematic-open-2d').click();
    await expect(page.getByTestId('graph-view-mode-2d')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('replay-cursor-label')).toContainText(/sequence/);
  });

  test('reduced motion exposes accessibility fallback without requiring motion', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(REPLAY_PATH);
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(page.getByTestId('cinematic-a11y-fallback')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('cinematic-a11y-caption')).toBeVisible();
    await expect(page.getByTestId('cinematic-a11y-beat-list')).toBeVisible();
    await expect(page.getByTestId('cinematic-reduced-motion-badge')).toBeVisible();
  });

  test('unavailable replay fails safely for cinematic mode', async ({ page }) => {
    await page.goto('/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FZ0');
    await expect(page.getByTestId('historical-mode-banner')).toBeVisible();
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(page.getByTestId('cinematic-error')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('cinematic-error-code')).toContainText(/CINEMATIC_|REPLAY_/);
  });

  test('narrow layout keeps cinematic controls usable', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto(REPLAY_PATH);
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(page.getByTestId('cinematic-transport-controls')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('cinematic-a11y-fallback')).toBeVisible();
    await expect(page.getByTestId('cinematic-mode-toggle')).toBeVisible();
  });
});
