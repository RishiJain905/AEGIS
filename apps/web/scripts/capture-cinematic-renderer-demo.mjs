import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { copyFileSync } from 'node:fs';

const ARTIFACTS = '/opt/cursor/artifacts/phase27-screenshots';
const EVIDENCE = '/workspace/docs/handoffs/evidence/27-threejs-semantic-renderer';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const REPLAY = '/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

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

await page.goto(`${BASE}${RUN}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=visualization-slot]', { timeout: 60_000 });
await page.waitForSelector('[data-testid=graph-view-mode-toggle]', { timeout: 60_000 });
await page.waitForTimeout(1500);

await shot('27-command-centre-with-3d-toggle', async () => {
  await page.waitForSelector('[data-testid=operational-graph-view]');
});

await shot('27-2d-operational-graph-silent-relay', async () => {
  await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
  await page.waitForSelector('[data-testid=graph-entity-inspector]');
});

await shot('27-selected-entity-inspector-2d', async () => {});

await page.getByTestId('graph-view-mode-3d').click();
await page.waitForTimeout(1000);

const fallbackVisible = await page.getByTestId('cinematic-capability-fallback').isVisible();
if (fallbackVisible) {
  await shot('27-capability-fallback', async () => {});
  await page.getByTestId('cinematic-return-2d').click();
} else {
  await page.waitForSelector('[data-testid=cinematic-graph-view]', { timeout: 30000 });
  await shot('27-3d-semantic-graph-silent-relay', async () => {});

  await shot('27-3d-nodes-edges-risk-status', async () => {
    await page.getByTestId('cinematic-entity-asset:svc-api-gateway').click();
  });

  await shot('27-selected-entity-inspector-3d', async () => {
    await page.waitForSelector('[data-testid=graph-entity-inspector]');
  });

  await shot('27-camera-controls-reset', async () => {
    await page.getByTestId('cinematic-reset-camera').click();
  });

  await page.getByTestId('graph-view-mode-2d').click();
  await page.waitForSelector('[data-testid=operational-graph-view]');
  await shot('27-mode-switch-preserves-selection-2d', async () => {});
}

await page.emulateMedia({ reducedMotion: 'reduce' });
await page.getByTestId('graph-view-mode-3d').click();
await page.waitForTimeout(800);
await shot('27-reduced-motion-or-fallback', async () => {});
await page.emulateMedia({ reducedMotion: 'no-preference' });

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}${RUN}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=graph-view-mode-toggle]', { timeout: 60_000 });
await page.waitForTimeout(1000);
await page.getByTestId('graph-view-mode-3d').click();
await page.waitForTimeout(800);
await shot('27-narrow-responsive-3d-or-fallback', async () => {});

await page.setViewportSize({ width: 1440, height: 900 });
await page.goto(`${BASE}${REPLAY}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
try {
  await page.waitForSelector('[data-testid=visualization-slot]', { timeout: 60_000 });
  await page.waitForTimeout(1500);
  const toggle = page.getByTestId('graph-view-mode-toggle');
  if (await toggle.isVisible()) {
    await page.getByTestId('graph-view-mode-3d').click();
    await page.waitForTimeout(800);
    await shot('27-replay-historical-3d-or-fallback', async () => {});
  } else {
    await shot('27-replay-slot-without-graph-yet', async () => {});
  }
} catch {
  await shot('27-replay-unavailable', async () => {});
}

// Demonstrate safe degradation: 2D remains available after 3D attempt
await page.goto(`${BASE}${RUN}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=graph-view-mode-toggle]', { timeout: 60_000 });
await page.waitForTimeout(1000);
await shot('27-2d-still-available-after-3d-attempt', async () => {
  await page.getByTestId('graph-view-mode-2d').click();
  await page.waitForSelector('[data-testid=operational-graph-view]');
});

const video = page.video();
await context.close();
await browser.close();

if (video) {
  const videoPath = await video.path();
  const dest = `${ARTIFACTS}/27-cinematic-navigation.webm`;
  copyFileSync(videoPath, dest);
  copyFileSync(dest, `${EVIDENCE}/27-cinematic-navigation.webm`);
  console.log(`wrote ${dest}`);
}

console.log('Phase 27 visual capture complete');
