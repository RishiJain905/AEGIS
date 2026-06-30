import { test, expect } from '@playwright/test';

test.describe('design system showcase', () => {
  test('navigates showcase and exposes status text', async ({ page }) => {
    await page.goto('/design-system');
    await expect(page.getByRole('heading', { name: 'Command-Centre Design System' })).toBeVisible();
    await expect(page.getByLabel('Status: Suspicious — elevated watch').first()).toBeVisible();
    await expect(page.getByLabel('Status: Compromised — confirmed breach').first()).toBeVisible();
    await expect(page.getByTestId('disconnected-state')).toBeVisible();
  });

  test('supports keyboard interaction for dialog', async ({ page }) => {
    await page.goto('/design-system');
    await page.getByRole('tab', { name: 'Overlays' }).click();
    await page.getByTestId('open-dialog').focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('supports keyboard interaction for menu', async ({ page }) => {
    await page.goto('/design-system');
    await page.getByRole('tab', { name: 'Overlays' }).click();
    await page.getByTestId('open-menu').click();
    const viewEvidence = page.getByRole('menuitem', { name: 'View evidence' });
    const escalate = page.getByRole('menuitem', { name: 'Escalate incident' });
    await expect(viewEvidence).toBeVisible();
    await expect(escalate).toBeVisible();
    await viewEvidence.focus();
    await page.keyboard.press('ArrowDown');
    await expect(escalate).toBeFocused();
  });
});
