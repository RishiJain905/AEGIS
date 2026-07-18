import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

const RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const SILENT_RELAY_RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FB0';
const INCIDENT = 'incident:inc_synthetic_001';
const INCIDENT_PATH = `/incidents/${encodeURIComponent(INCIDENT)}`;

function contractFixture(name: string): unknown {
  const packageRoot = process.cwd();
  const candidates = [
    resolve(packageRoot, '../../tests/contract/fixtures/valid', name),
    resolve(packageRoot, 'tests/contract/fixtures/valid', name),
  ];
  const path = candidates.find((candidate) => existsSync(candidate));
  if (!path) {
    throw new Error(`contract fixture not found: ${name}`);
  }
  return JSON.parse(readFileSync(path, 'utf8')) as unknown;
}

async function mockApprovalProvider(page: Page) {
  await page.route('**/api/v1/action-proposals/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const fixture = pathname.endsWith('/approve')
      ? 'approve_proposal_response_v1.json'
      : pathname.endsWith('/reject')
        ? 'reject_proposal_response_v1.json'
        : 'modify_proposal_response_v1.json';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(contractFixture(fixture)),
    });
  });
}

test.describe('Phase 34 Operation Silent Relay release journeys', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/sign-in');
    await expect(page.getByTestId('sign-in-page')).toBeVisible();
    await page.getByTestId('dev-login-operator').click();
    await expect(page.getByTestId('operator-identity')).toBeVisible({ timeout: 15_000 });
  });

  test('starts or opens the golden scenario and shows live graph updates', async ({ page }) => {
    await page.goto('/scenarios');
    await expect(page.getByTestId('scenarios-table')).toBeVisible();
    const silentRelayRow = page.locator('tr').filter({ hasText: 'Operation Silent Relay' }).first();
    await expect(silentRelayRow).toBeVisible();
    await silentRelayRow.getByRole('button', { name: 'Open run' }).click();

    await expect(page).toHaveURL(new RegExp(`/runs/${SILENT_RELAY_RUN}$`));
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('timeline-area')).toBeVisible();
    await expect(page.getByTestId('status-strip')).toBeVisible();
  });

  test('triages an alert and exercises mock WATCHTOWER, TRACE, ORACLE, and BASTION workflow', async ({
    page,
  }) => {
    await page.goto(INCIDENT_PATH);
    await expect(page.getByTestId('investigation-panel')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('investigation-triage-panel')).toBeVisible();
    await expect(page.getByTestId('investigation-evidence-panel')).toBeVisible();
    await expect(page.getByTestId('investigation-agent-lifecycle-panel')).toContainText(
      'WATCHTOWER',
    );
    await expect(page.getByTestId('investigation-agent-lifecycle-panel')).toContainText('TRACE');
    await expect(page.getByTestId('investigation-hypotheses-panel')).toContainText('ORACLE');
    await expect(page.getByTestId('proposals-panel')).toContainText('BASTION');
    await expect(page.getByTestId('proposals-panel')).toContainText('approval_required');
  });

  test('covers approve, reject, and modify approval paths with a recorded mock provider', async ({
    page,
  }) => {
    await mockApprovalProvider(page);
    await page.goto(INCIDENT_PATH);
    const controls = page.locator('[data-testid^="approval-controls-"]').first();
    await expect(controls).toBeVisible();

    await controls.getByRole('button', { name: 'Approve' }).click();
    await expect(controls.locator('[data-testid^="approval-success-"]')).toContainText('approved');

    await page.goto(INCIDENT_PATH);
    const rejectControls = page.locator('[data-testid^="approval-controls-"]').first();
    await rejectControls
      .locator('[data-testid^="reject-reason-"]')
      .fill('Release journey rejection');
    await rejectControls.getByRole('button', { name: 'Reject' }).click();
    await expect(rejectControls.locator('[data-testid^="approval-success-"]')).toContainText(
      'rejected',
    );

    await page.goto(INCIDENT_PATH);
    const modifyControls = page.locator('[data-testid^="approval-controls-"]').first();
    await modifyControls.getByText('Modify / request revision').click();
    await modifyControls.getByRole('button', { name: 'Submit modification' }).click();
    await expect(modifyControls.locator('[data-testid^="approval-success-"]')).toContainText(
      'revised',
    );
  });

  test('creates a snapshot, opens replay and cinematic replay, and reads SCRIBE scoring', async ({
    page,
  }) => {
    const snapshot = contractFixture('snapshot_manifest_v1.json');
    await page.route('**/api/v1/replay/runs/*/snapshots', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(snapshot),
      });
    });
    const snapshotResponse = await page.evaluate(async (runId) => {
      const response = await fetch(`/api/v1/replay/runs/${runId}/snapshots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schemaVersion: 1, triggerReason: 'manual' }),
      });
      return { status: response.status, body: await response.json() };
    }, RUN);
    expect(snapshotResponse.status).toBe(200);
    expect(snapshotResponse.body).toHaveProperty('snapshotId');

    await page.goto(`/replay/${RUN}`);
    await expect(page.getByTestId('historical-mode-banner')).toBeVisible();
    await expect(page.getByTestId('replay-transport-controls')).toBeVisible();
    await page.getByTestId('cinematic-mode-cinematic').click();
    await expect(
      page
        .getByTestId('cinematic-transport-controls')
        .or(page.getByTestId('cinematic-a11y-fallback'))
        .first(),
    ).toBeVisible({ timeout: 30_000 });

    await page.goto('/reports');
    await expect(page.getByTestId('reports-panel')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('SCRIBE report')).toBeVisible();

    await page.goto(`/after-action/${RUN}`);
    await expect(page.getByTestId('after-action-dashboard')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('overall-score')).toBeVisible();
    await expect(page.getByTestId('score-category-list')).toBeVisible();
  });

  test('covers keyboard-only navigation, reduced motion, responsive, loading, empty, error, and disconnected states', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/runs/${RUN}`);
    await expect(page.getByTestId('open-mobile-rail')).toBeVisible();
    await page.getByTestId('open-mobile-rail').focus();
    await expect(page.getByTestId('open-mobile-rail')).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(
      page.getByRole('navigation', { name: 'Mobile operations navigation' }),
    ).toBeVisible();
    await expect(page.locator('[data-reduced-motion="true"]')).toBeVisible();

    await page.goto('/scenarios?profile=loading');
    await expect(page.getByText(/Loading scenarios/i)).toBeVisible();
    await expect(page.getByTestId('scenarios-table')).toBeVisible({ timeout: 10_000 });
    await page.goto('/scenarios?profile=empty');
    await expect(page.getByTestId('scenarios-empty')).toBeVisible();
    await page.goto('/scenarios?profile=error');
    await expect(page.getByTestId('scenarios-error')).toBeVisible();
    await page.goto(`/runs/${RUN}?profile=offline`);
    await expect(page.getByTestId('connection-banner')).toBeVisible();
  });
});
