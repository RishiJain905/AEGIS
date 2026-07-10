import { chromium } from '@playwright/test';
import { mkdirSync, copyFileSync } from 'node:fs';

const ARTIFACTS = '/opt/cursor/artifacts/phase28-screenshots';
const EVIDENCE = '/workspace/docs/handoffs/evidence/28-cinematic-incident-replay';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const REPLAY = '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const REPLAY_BAD = '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FZ0';

mkdirSync(ARTIFACTS, { recursive: true });
mkdirSync(EVIDENCE, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: ARTIFACTS, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();

async function shot(name, fn) {
  if (fn) {
    await fn();
  }
  await page.waitForTimeout(700);
  const path = `${ARTIFACTS}/${name}.png`;
  await page.screenshot({ path, fullPage: false });
  copyFileSync(path, `${EVIDENCE}/${name}.png`);
  console.log(`wrote ${path}`);
}

await page.goto(`${BASE}${REPLAY}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=historical-mode-banner]', { timeout: 60_000 });
await page.waitForSelector('[data-testid=cinematic-mode-toggle]', { timeout: 60_000 });
await page.waitForTimeout(1200);

await shot('28-silent-relay-replay-available', async () => {
  await page.waitForSelector('[data-testid=replay-transport-controls]');
});

await page.getByTestId('cinematic-mode-cinematic').click();
await page.waitForSelector('[data-testid=cinematic-transport-controls]', { timeout: 30_000 });
await page.waitForTimeout(1500);

await shot('28-cinematic-mode-loaded-historical-label', async () => {
  await page.waitForSelector('[data-testid=cinematic-historical-label]');
});

await shot('28-camera-focus-incident-origin', async () => {
  const incident = page.getByTestId('cinematic-a11y-beat-beat_incident_origin_001');
  if (await incident.count()) {
    await incident.click();
  } else {
    await page.getByTestId('cinematic-next-beat').click();
    await page.getByTestId('cinematic-next-beat').click();
  }
  await page.waitForTimeout(800);
});

await shot('28-camera-focus-evidence-assets', async () => {
  const evidence = page.getByTestId('cinematic-a11y-beat-beat_evidence_focus_001');
  if (await evidence.count()) {
    await evidence.click();
  } else {
    await page.getByTestId('cinematic-next-beat').click();
  }
  await page.waitForTimeout(800);
});

await shot('28-agent-activity-cinematic', async () => {
  const agent = page.getByTestId('cinematic-a11y-beat-beat_agent_investigation_001');
  if (await agent.count()) {
    await agent.click();
  }
  await page.waitForTimeout(600);
});

await shot('28-risk-or-propagation-cinematic', async () => {
  const risk = page.getByTestId('cinematic-a11y-beat-beat_risk_change_001');
  if (await risk.count()) {
    await risk.click();
  }
  await page.waitForTimeout(600);
});

await shot('28-proposal-approval-report-context', async () => {
  const approval = page.getByTestId('cinematic-a11y-beat-beat_approval_moment_001');
  if (await approval.count()) {
    await approval.click();
  } else {
    const proposal = page.getByTestId('cinematic-a11y-beat-beat_proposal_focus_001');
    if (await proposal.count()) {
      await proposal.click();
    }
  }
  await page.waitForTimeout(600);
});

await shot('28-timeline-cursor-synchronized', async () => {
  await expectVisible(page, 'cinematic-sync-label');
  await expectVisible(page, 'replay-cursor-label');
});

await shot('28-mode-switch-normal-and-cinematic', async () => {
  await page.getByTestId('cinematic-mode-normal').click();
  await page.waitForTimeout(400);
  await page.getByTestId('cinematic-mode-cinematic').click();
  await page.waitForSelector('[data-testid=cinematic-transport-controls]');
});

await page.emulateMedia({ reducedMotion: 'reduce' });
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid=cinematic-mode-cinematic]', { timeout: 60_000 });
await page.getByTestId('cinematic-mode-cinematic').click();
await page.waitForSelector('[data-testid=cinematic-a11y-fallback]', { timeout: 30_000 });
await shot('28-reduced-motion-accessibility-fallback', async () => {
  await page.waitForSelector('[data-testid=cinematic-a11y-beat-list]');
});
await page.emulateMedia({ reducedMotion: 'no-preference' });

await page.goto(`${BASE}${REPLAY_BAD}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=cinematic-mode-cinematic]', { timeout: 60_000 });
await page.getByTestId('cinematic-mode-cinematic').click();
await shot('28-safe-error-unavailable-replay', async () => {
  await page.waitForSelector('[data-testid=cinematic-error]', { timeout: 30_000 });
});

await page.setViewportSize({ width: 768, height: 900 });
await page.goto(`${BASE}${REPLAY}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=cinematic-mode-cinematic]', { timeout: 60_000 });
await page.getByTestId('cinematic-mode-cinematic').click();
await page.waitForSelector('[data-testid=cinematic-transport-controls]', { timeout: 30_000 });
await shot('28-narrow-responsive-cinematic', async () => {
  await page.waitForSelector('[data-testid=cinematic-a11y-fallback]');
});

// Short recording of camera movement / transitions / controls
await page.setViewportSize({ width: 1440, height: 900 });
await page.goto(`${BASE}${REPLAY}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=cinematic-mode-cinematic]', { timeout: 60_000 });
await page.getByTestId('cinematic-mode-cinematic').click();
await page.waitForSelector('[data-testid=cinematic-transport-controls]', { timeout: 30_000 });
await page.getByTestId('cinematic-next-beat').click();
await page.waitForTimeout(500);
await page.getByTestId('cinematic-next-beat').click();
await page.waitForTimeout(500);
await page.getByTestId('cinematic-next-chapter').click();
await page.waitForTimeout(500);
await page.getByTestId('cinematic-play-pause').click();
await page.waitForTimeout(2000);
await page.getByTestId('cinematic-play-pause').click();
await page.getByTestId('cinematic-mode-normal').click();
await page.waitForTimeout(400);
await page.getByTestId('cinematic-mode-cinematic').click();
await page.waitForTimeout(800);

const video = page.video();
await context.close();
await browser.close();

if (video) {
  const videoPath = await video.path();
  const dest = `${EVIDENCE}/28-cinematic-incident-replay.webm`;
  copyFileSync(videoPath, dest);
  copyFileSync(videoPath, `${ARTIFACTS}/28-cinematic-incident-replay.webm`);
  console.log(`wrote ${dest}`);
}

async function expectVisible(page, testId) {
  await page.waitForSelector(`[data-testid=${testId}]`, { timeout: 15_000 });
}

console.log('Phase 28 visual capture complete');
