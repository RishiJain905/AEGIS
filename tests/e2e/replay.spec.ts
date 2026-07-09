import { expect, test } from '@playwright/test';

const REPLAY_PATH = '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

test.describe('Phase 26 replay frontend', () => {
  test('opens historical replay with distinct mode labeling and transport controls', async ({
    page,
  }) => {
    await page.goto(REPLAY_PATH);
    await expect(page.getByTestId('historical-mode-banner')).toBeVisible();
    await expect(page.getByTestId('historical-mode-badge')).toContainText(/Historical|Playback/);
    await expect(page.getByTestId('replay-read-only-badge')).toContainText('Read-only');
    await expect(page.getByTestId('replay-transport-controls')).toBeVisible();
    await expect(page.getByTestId('replay-scrubber')).toBeVisible();
    await expect(page.getByTestId('visualization-slot')).toBeVisible();
    await expect(page.getByTestId('timeline-area')).toBeVisible();
    await expect(page.getByTestId('live-run-controls')).toHaveCount(0);
  });

  test('scrubs timeline and reconstructs inspector/graph state', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await expect(page.getByTestId('replay-scrubber')).toBeVisible();
    await page.getByTestId('replay-jump-start').click();
    await expect(page.getByTestId('replay-cursor-label')).toContainText('sequence 0');
    await page.getByTestId('replay-scrubber').fill('250');
    await expect(page.getByTestId('replay-cursor-label')).toContainText('sequence 250');
    await expect(page.getByTestId('replay-inspector-cursor')).toContainText('250');
  });

  test('play pause step and speed controls move the shared cursor', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await page.getByTestId('replay-jump-start').click();
    await page.getByTestId('replay-step-forward').click();
    await expect(page.getByTestId('replay-cursor-label')).toContainText('sequence 1');
    await page.getByTestId('replay-speed-2x').click();
    await expect(page.getByTestId('replay-speed-label')).toHaveText('2x');
    await page.getByTestId('replay-play-pause').click();
    await expect(page.getByTestId('replay-play-pause')).toHaveAttribute('aria-pressed', 'true');
    await page.getByTestId('replay-play-pause').click();
    await expect(page.getByTestId('replay-play-pause')).toHaveAttribute('aria-pressed', 'false');
  });

  test('incident bookmarks jump and comparison shows differences', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await expect(page.getByTestId('replay-bookmarks')).toBeVisible({ timeout: 15_000 });
    const bookmark = page.locator('[data-testid^="replay-bookmark-"]').first();
    await expect(bookmark).toBeVisible();
    await bookmark.click();
    await expect(page.getByTestId('replay-cursor-label')).toContainText('sequence');
    await page.getByTestId('replay-compare-mark-left').click();
    await page.getByTestId('replay-jump-end').click();
    await page.getByTestId('replay-compare-mark-right').click();
    await expect(page.getByTestId('replay-comparison-result')).toBeVisible({ timeout: 15_000 });
  });

  test('reload reconstructs the selected replay state', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await page.getByTestId('replay-scrubber').fill('180');
    await expect(page.getByTestId('replay-cursor-label')).toContainText('sequence 180');
    await page.reload();
    await expect(page.getByTestId('historical-mode-banner')).toBeVisible();
    await expect(page.getByTestId('replay-transport-controls')).toBeVisible();
  });

  test('unavailable replay data produces a safe actionable error', async ({ page }) => {
    await page.goto('/replay/run_replay_unavailable');
    await expect(page.getByTestId('visualization-slot')).toContainText(/unavailable|corrupted|incompatible/i);
    await expect(page.getByTestId('replay-error-code')).toContainText('REPLAY_NOT_FOUND');
  });

  test('keyboard controls and narrow layout remain usable', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto(REPLAY_PATH);
    await expect(page.getByTestId('replay-transport-controls')).toBeVisible();
    await expect(page.getByTestId('open-mobile-rail')).toBeVisible();
    await page.getByTestId('replay-jump-start').click();
    await page.locator('body').click();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByTestId('replay-cursor-label')).toContainText('sequence 1');
    await page.keyboard.press(']');
    await expect(page.getByTestId('replay-speed-label')).toHaveText('2x');
  });

  test('return to live navigates to the live run route', async ({ page }) => {
    await page.goto(REPLAY_PATH);
    await page.getByTestId('return-to-live').click();
    await expect(page).toHaveURL(/\/runs\/run_01ARZ3NDEKTSV4RRFFQ69G5FAV/);
  });
});
