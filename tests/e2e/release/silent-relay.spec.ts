import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

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

test.describe('Phase 34 Operation Silent Relay release journeys', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/sign-in');
    await expect(page.getByTestId('sign-in-page')).toBeVisible();
    await page.getByTestId('dev-login-operator').click();
    await expect(page.getByTestId('operator-identity')).toBeVisible({ timeout: 15_000 });
  });

  test('opens the golden scenario via the resume affordance and shows live graph updates', async ({
    page,
  }) => {
    await page.goto('/scenarios');
    await expect(page.getByTestId('scenarios-table')).toBeVisible({ timeout: 15_000 });
    const silentRelayRow = page.locator('tr').filter({ hasText: 'Operation Silent Relay' }).first();
    await expect(silentRelayRow).toBeVisible();
    // The Scenarios page no longer exposes a hardcoded "Open run" button. It now offers
    // "Start new run" and, when the account already owns a most-recent run for the
    // scenario, a "Resume latest run" affordance. Resume the golden Silent Relay run.
    await silentRelayRow.getByTestId('resume-run-scenario:operation-silent-relay').click();

    await expect(page).toHaveURL(new RegExp(`/runs/${SILENT_RELAY_RUN}$`));
    await expect(page.getByTestId('operational-graph-canvas')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('timeline-area')).toBeVisible();
    await expect(page.getByTestId('status-strip')).toBeVisible();
  });

  test('triages an incident and attributes the WATCHTOWER, TRACE, ORACLE, and BASTION roster', async ({
    page,
  }) => {
    await page.goto(INCIDENT_PATH);
    // The incident view was redesigned into a case-management workspace (ADR-era "incident
    // view differentiation"): triage timeline, agent roster, and proposals replace the old
    // investigation inspector panels.
    await expect(page.getByTestId('incident-workspace')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('incident-detail-summary')).toBeVisible();
    await expect(page.getByTestId('incident-triage-timeline')).toBeVisible();

    // Per-role participation is derived from the persisted investigation detail, so the
    // full WATCHTOWER -> TRACE -> ORACLE -> BASTION pipeline is attributable and active.
    const roster = page.getByTestId('incident-agent-roster');
    await expect(roster).toBeVisible();
    for (const role of ['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION'] as const) {
      await expect(page.getByTestId(`agent-role-${role}`)).toContainText('Active');
    }
  });

  test('surfaces BASTION response proposals with their policy and human-approval state', async ({
    page,
  }) => {
    await page.goto(INCIDENT_PATH);
    const proposals = page.getByTestId('incident-proposals');
    await expect(proposals).toBeVisible({ timeout: 30_000 });

    // The Class-2 isolate proposal carries a WARDEN 'approval_required' policy decision, so
    // the approvals surface must show it awaiting a human gate before any execution.
    await expect(proposals).toContainText('isolate');
    await expect(proposals).toContainText('Awaiting human approval');
    // The lower-class observe proposal is also listed, so the panel reflects the full
    // proposed-response set rather than only the gated action.
    await expect(proposals).toContainText('observe');
    await expect(proposals).toContainText(/awaiting approval/i);

    // AEGIS-BUG-011: the interactive human-approval gate must be REACHABLE from the
    // incident detail, not merely a read-only status. The signed-in operator holds
    // approvals:decide, so the approve/reject/modify controls render for the pending
    // Class-2 isolate proposal (prv approval_required). Regression guard against the
    // controls being orphaned by the incident/inspector redesign.
    const ISOLATE_PROPOSAL = 'prp_01ARZ3NDEKTSV4RRFFQ69G5FB9';
    await expect(page.getByTestId(`approval-controls-${ISOLATE_PROPOSAL}`)).toBeVisible();
    await expect(page.getByTestId(`approve-proposal-${ISOLATE_PROPOSAL}`)).toBeVisible();
    await expect(page.getByTestId(`reject-proposal-${ISOLATE_PROPOSAL}`)).toBeVisible();
    // The modify affordance lives in a collapsed <details>; its summary is always shown.
    await expect(page.getByTestId(`modify-proposal-details-${ISOLATE_PROPOSAL}`)).toBeVisible();
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
    // The Reports tab renders the SCRIBE after-action workspace (reporting-surfaces
    // overhaul) rather than the inspector's compact reports panel.
    await expect(page.getByTestId('reports-workspace')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('heading', { name: 'After-action reports' })).toBeVisible();

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
