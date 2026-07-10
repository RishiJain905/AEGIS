import { chromium } from '@playwright/test';
import { mkdirSync, copyFileSync } from 'node:fs';

const ARTIFACTS = '/opt/cursor/artifacts/phase29-screenshots';
const EVIDENCE = '/workspace/docs/handoffs/evidence/29-scoring-and-after-action';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const RUN = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const BAD = 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ0';
const AFTER = `/after-action/${RUN}`;
const AFTER_BAD = `/after-action/${BAD}`;

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
  await page.waitForTimeout(600);
  const path = `${ARTIFACTS}/${name}.png`;
  await page.screenshot({ path, fullPage: false });
  copyFileSync(path, `${EVIDENCE}/${name}.png`);
  console.log(`wrote ${path}`);
}

await page.goto(`${BASE}${AFTER}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=after-action-dashboard]', { timeout: 60_000 });

await shot('29-completed-run-ready-for-after-action');
await shot('29-overall-score-and-grade');
await shot('29-score-category-breakdowns', async () => {
  await page.getByTestId('score-category-list').scrollIntoViewIfNeeded();
});
await shot('29-score-explanation-rule-ids', async () => {
  await page.getByTestId('score-component-criterion-evidence-coverage').click();
  await page.waitForSelector('[data-testid=score-explanation]');
});
await shot('29-timeline-review-decisions', async () => {
  await page.getByTestId('timeline-review').scrollIntoViewIfNeeded();
});
await shot('29-missed-evidence', async () => {
  await page.getByTestId('missed-evidence-list').scrollIntoViewIfNeeded();
});
await shot('29-agent-vs-operator-decisions', async () => {
  await page.getByTestId('timeline-review').scrollIntoViewIfNeeded();
});
await shot('29-valid-alternatives-counterfactual', async () => {
  await page.getByTestId('valid-alternatives-list').scrollIntoViewIfNeeded();
});
await shot('29-scribe-integration', async () => {
  await page.getByTestId('scribe-integration').scrollIntoViewIfNeeded();
});
await shot('29-export-metadata-integrity', async () => {
  await page.getByTestId('export-metadata').scrollIntoViewIfNeeded();
});

await page.getByTestId('jump-to-replay').click();
await page.waitForTimeout(1500);
await shot('29-jump-to-replay-from-after-action');

await page.goto(`${BASE}${AFTER_BAD}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=after-action-error]', { timeout: 60_000 });
await shot('29-safe-error-incomplete-scoring');

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}${AFTER}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=after-action-dashboard]', { timeout: 60_000 });
await shot('29-narrow-responsive-layout');

// Short navigation recording already captured via recordVideo
await page.goto(`${BASE}${AFTER}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=after-action-dashboard]', { timeout: 60_000 });
await page.getByTestId('score-component-criterion-detection-speed').click();
await page.waitForTimeout(400);
await page.getByTestId('score-component-criterion-hypothesis-quality').click();
await page.waitForTimeout(400);
await page.getByTestId('valid-alternatives-list').scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
await page.getByTestId('missed-evidence-list').scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
await page.getByTestId('jump-to-replay').click();
await page.waitForTimeout(1200);

const video = page.video();
await context.close();
await browser.close();
if (video) {
  const videoPath = await video.path();
  copyFileSync(videoPath, `${EVIDENCE}/29-after-action-navigation.webm`);
  copyFileSync(videoPath, `${ARTIFACTS}/29-after-action-navigation.webm`);
  console.log(`wrote ${EVIDENCE}/29-after-action-navigation.webm`);
}
console.log('Phase 29 capture complete');
