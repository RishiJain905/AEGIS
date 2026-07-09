#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../../..');
const OUT = '/opt/cursor/artifacts/screenshots';
const VIDEO_OUT = '/opt/cursor/artifacts/videos';
const WEB_BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const RUN_ID = process.env.REPLAY_DEMO_RUN_ID ?? 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const ERROR_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ0';

mkdirSync(OUT, { recursive: true });
mkdirSync(VIDEO_OUT, { recursive: true });

const env = {
  ...process.env,
  PATH: `${process.env.HOME}/.local/bin:${process.env.PATH}`,
  NEXT_PUBLIC_AEGIS_DATA_SOURCE: process.env.NEXT_PUBLIC_AEGIS_DATA_SOURCE ?? 'fixture',
  WEB_PORT: '3000',
};

const web = spawn('pnpm', ['--filter', '@aegis/web', 'start', '--port', '3000'], {
  cwd: ROOT,
  env,
  stdio: 'ignore',
});

async function waitForUrl(url, attempts = 90) {
  for (let index = 0; index < attempts; index += 1) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status < 500) return;
    } catch {
      // retry
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 1000));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

await waitForUrl(`${WEB_BASE}/scenarios`);

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1200 },
  recordVideo: { dir: VIDEO_OUT, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();

async function shot(name) {
  const path = `${OUT}/26-${name}.png`;
  await page.screenshot({ path, fullPage: true });
  console.log(`wrote ${path}`);
}

await page.goto(`${WEB_BASE}/runs/${RUN_ID}`, {
  waitUntil: 'domcontentloaded',
  timeout: 60_000,
});
await page.waitForSelector('[data-testid="command-centre-shell"]', { timeout: 60_000 });
await page.waitForTimeout(1500);
await shot('live-or-completed-run-available');

await page.goto(`${WEB_BASE}/replay/${RUN_ID}`, {
  waitUntil: 'domcontentloaded',
  timeout: 60_000,
});
await page.waitForSelector('[data-testid="historical-mode-banner"]', { timeout: 60_000 });
await page.waitForTimeout(1500);
await shot('replay-route-historical-labeling');
await shot('replay-timeline-scrubbing-controls');
await shot('replay-play-pause-step-speed');

await page.getByTestId('replay-jump-start').click();
await page.waitForTimeout(800);
await shot('reconstructed-graph-early');
await shot('incident-timeline-synced-early');

await page.getByTestId('replay-scrubber').fill('400');
await page.waitForTimeout(1000);
await shot('reconstructed-graph-later');
await shot('incident-timeline-synced-later');

await page.getByTestId('replay-jump-end').click();
await page.waitForTimeout(800);
await shot('inspector-historical-state');

const bookmark = page.locator('[data-testid^="replay-bookmark-"]').first();
if (await bookmark.count()) {
  await bookmark.click();
  await page.waitForTimeout(800);
}
await shot('incident-bookmarks');

await page.getByTestId('replay-compare-mark-left').click();
await page.getByTestId('replay-jump-end').click();
await page.getByTestId('replay-compare-mark-right').click();
await page.waitForTimeout(1000);
await shot('state-comparison');

// Motion recording segment
await page.getByTestId('replay-jump-start').click();
await page.waitForTimeout(400);
await page.getByTestId('replay-speed-2x').click();
await page.getByTestId('replay-play-pause').click();
await page.waitForTimeout(2500);
await page.getByTestId('replay-play-pause').click();
if (await bookmark.count()) {
  await bookmark.click();
  await page.waitForTimeout(600);
}
await page.getByTestId('replay-scrubber').fill('320');
await page.waitForTimeout(800);

await page.setViewportSize({ width: 768, height: 900 });
await page.goto(`${WEB_BASE}/replay/${RUN_ID}`, {
  waitUntil: 'domcontentloaded',
  timeout: 60_000,
});
await page.waitForSelector('[data-testid="replay-transport-controls"]', { timeout: 60_000 });
await page.waitForTimeout(1000);
await shot('responsive-narrow-layout');

await page.setViewportSize({ width: 1440, height: 1200 });
await page.goto(`${WEB_BASE}/replay/${ERROR_RUN_ID}`, {
  waitUntil: 'domcontentloaded',
  timeout: 60_000,
});
await page.waitForSelector('[data-testid="visualization-slot"]', { timeout: 60_000 });
await page.waitForTimeout(800);
await shot('safe-error-unavailable-replay');

const video = page.video();
await context.close();
await browser.close();
if (video) {
  const videoPath = await video.path();
  const target = `${VIDEO_OUT}/26-replay-frontend-motion.webm`;
  const { copyFileSync } = await import('node:fs');
  copyFileSync(videoPath, target);
  console.log(`wrote ${target}`);
}

writeFileSync(
  `${OUT}/26-capture-manifest.json`,
  JSON.stringify(
    {
      runId: RUN_ID,
      errorRunId: ERROR_RUN_ID,
      dataSource: env.NEXT_PUBLIC_AEGIS_DATA_SOURCE,
      capturedAt: new Date().toISOString(),
      screenshots: [
        '26-live-or-completed-run-available.png',
        '26-replay-route-historical-labeling.png',
        '26-replay-timeline-scrubbing-controls.png',
        '26-replay-play-pause-step-speed.png',
        '26-reconstructed-graph-early.png',
        '26-reconstructed-graph-later.png',
        '26-incident-timeline-synced-early.png',
        '26-incident-timeline-synced-later.png',
        '26-inspector-historical-state.png',
        '26-incident-bookmarks.png',
        '26-state-comparison.png',
        '26-safe-error-unavailable-replay.png',
        '26-responsive-narrow-layout.png',
      ],
      recording: '26-replay-frontend-motion.webm',
    },
    null,
    2,
  ),
);

web.kill('SIGTERM');
console.log('Phase 26 capture complete');
process.exit(0);
