import { expect, test } from '@playwright/test';

test.describe('Phase 30 authentication', () => {
  test('unauthenticated user is sent to sign-in', async ({ page }) => {
    await page.goto('/scenarios');
    await expect(page.getByTestId('sign-in-page')).toBeVisible({ timeout: 15_000 });
  });

  test('operator can sign in and see identity', async ({ page }) => {
    await page.goto('/sign-in');
    await expect(page.getByTestId('sign-in-page')).toBeVisible();
    await page.getByTestId('dev-login-operator').click();
    await expect(page.getByTestId('operator-identity')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('operator-display-name')).toContainText('Operator Alpha');
    await expect(page.getByTestId('operator-roles')).toContainText('operator');
  });

  test('viewer signs in without approval controls affordance path', async ({ page }) => {
    await page.goto('/sign-in');
    await page.getByTestId('dev-login-viewer').click();
    await expect(page.getByTestId('operator-identity')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('operator-roles')).toContainText('viewer');
  });

  test('logout returns to unauthenticated state', async ({ page }) => {
    await page.goto('/sign-in');
    await page.getByTestId('dev-login-operator').click();
    await expect(page.getByTestId('logout-button')).toBeVisible({ timeout: 15_000 });
    await page.getByTestId('logout-button').click();
    await expect(page.getByTestId('sign-in-page')).toBeVisible({ timeout: 15_000 });
  });
});
