import { test, expect } from '@playwright/test';

const INCIDENT_PATH = `/incidents/${encodeURIComponent('incident:inc_synthetic_001')}`;

test.describe('approval workflow', () => {
  test('shows proposal inspection and approval controls for approval_required proposals', async ({
    page,
  }) => {
    await page.goto(INCIDENT_PATH);
    await expect(page.getByTestId('inspector-panel')).toBeVisible();
    await expect(page.getByTestId('proposals-panel')).toBeVisible();

    const approvalRequiredCard = page.locator('[data-testid^="proposal-card-"]').filter({
      hasText: 'approval_required',
    });
    await expect(approvalRequiredCard.first()).toBeVisible();
    await expect(approvalRequiredCard.first().getByText('Expected consequences')).toBeVisible();
    await expect(approvalRequiredCard.first().getByText('Affected assets')).toBeVisible();
    await expect(approvalRequiredCard.first().getByText('WARDEN:')).toBeVisible();

    const controls = page.locator('[data-testid^="approval-controls-"]').first();
    await expect(controls).toBeVisible();
    await expect(controls.getByRole('button', { name: 'Approve' })).toBeVisible();
    await expect(controls.getByRole('button', { name: 'Reject' })).toBeVisible();
    await expect(controls.getByText('Modify / request revision')).toBeVisible();
  });

  test('keeps approval controls usable on a narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(INCIDENT_PATH);
    await expect(page.getByTestId('proposals-panel')).toBeVisible();
    const controls = page.locator('[data-testid^="approval-controls-"]').first();
    await expect(controls).toBeVisible();
    await expect(controls.getByRole('button', { name: 'Approve' })).toBeVisible();
  });

  test('shows lifecycle audit panel for proposals and policy decisions', async ({ page }) => {
    await page.goto(INCIDENT_PATH);
    await expect(page.getByTestId('proposal-lifecycle-panel')).toBeVisible();
    await expect(page.getByTestId('proposal-lifecycle-panel')).toContainText('status=');
    await expect(page.getByTestId('proposal-lifecycle-panel')).toContainText('policy');
  });
});
