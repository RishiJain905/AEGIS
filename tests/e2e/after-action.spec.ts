import { expect, test } from '@playwright/test';

const RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const BAD = 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ0';

test.describe('Phase 29 after-action experience', () => {
  test('loads overall score, categories, explanation, and timeline', async ({ page }) => {
    await page.goto(`/after-action/${RUN}`);
    await expect(page.getByTestId('after-action-dashboard')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('overall-score')).toBeVisible();
    await expect(page.getByTestId('overall-grade')).toBeVisible();
    await expect(page.getByTestId('score-category-list')).toBeVisible();
    await page.getByTestId('score-component-criterion-evidence-coverage').click();
    await expect(page.getByTestId('score-explanation')).toBeVisible();
    await expect(page.getByTestId('score-rule-id')).toContainText('rule-');
    await expect(page.getByTestId('timeline-review')).toBeVisible();
  });

  test('shows missed evidence, alternatives, SCRIBE, and export metadata', async ({ page }) => {
    await page.goto(`/after-action/${RUN}`);
    await expect(page.getByTestId('after-action-dashboard')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('missed-evidence-list')).toBeVisible();
    await expect(page.getByTestId('valid-alternatives-list')).toBeVisible();
    await expect(page.getByTestId('counterfactual-label').first()).toContainText(
      'non-authoritative',
    );
    await expect(page.getByTestId('scribe-integration')).toBeVisible();
    await expect(page.getByTestId('export-metadata')).toContainText('Integrity');
    await expect(page.getByTestId('coaching-text')).toContainText('non-authoritative');
  });

  test('jump to replay from after-action finding', async ({ page }) => {
    await page.goto(`/after-action/${RUN}`);
    await expect(page.getByTestId('jump-to-replay')).toBeVisible({ timeout: 60_000 });
    await page.getByTestId('jump-to-replay').click();
    await expect(page).toHaveURL(new RegExp(`/replay/${RUN}`));
  });

  test('safe error for incomplete scoring data', async ({ page }) => {
    await page.goto(`/after-action/${BAD}`);
    await expect(page.getByTestId('after-action-error')).toBeVisible({ timeout: 60_000 });
  });

  test('narrow layout keeps controls usable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/after-action/${RUN}`);
    await expect(page.getByTestId('after-action-dashboard')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('overall-score')).toBeVisible();
    await expect(page.getByTestId('score-category-list')).toBeVisible();
  });

  test('keyboard can focus score categories', async ({ page }) => {
    await page.goto(`/after-action/${RUN}`);
    await expect(page.getByTestId('after-action-dashboard')).toBeVisible({ timeout: 60_000 });
    await page.getByTestId('score-component-criterion-detection-speed').focus();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('score-explanation')).toBeVisible();
  });
});
