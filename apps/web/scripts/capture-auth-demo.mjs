import { chromium } from '@playwright/test';
import { mkdirSync, copyFileSync } from 'node:fs';

const ARTIFACTS = '/opt/cursor/artifacts/phase30-screenshots';
const EVIDENCE = '/workspace/docs/handoffs/evidence/phase-30';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';

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

// Unauthenticated sign-in
await page.goto(`${BASE}/scenarios`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=sign-in-page]', { timeout: 60_000 });
await shot('30-unauthenticated-sign-in');

// Operator login → command centre identity
await page.getByTestId('dev-login-operator').click();
await page.waitForSelector('[data-testid=operator-identity]', { timeout: 60_000 });
await shot('30-operator-authenticated-command-centre');
await shot('30-operator-identity-and-roles');

// Viewer role (read-only affordances)
await page.getByTestId('logout-button').click();
await page.waitForSelector('[data-testid=sign-in-page]', { timeout: 60_000 });
await page.getByTestId('dev-login-viewer').click();
await page.waitForSelector('[data-testid=operator-identity]', { timeout: 60_000 });
await shot('30-viewer-authenticated-read-only');

// Protected after-action / replay surfaces (viewer can read if permitted)
await page.goto(`${BASE}/after-action/run_01ARZ3NDEKTSV4RRFFQ69G5FAV`, {
  waitUntil: 'domcontentloaded',
  timeout: 60_000,
});
await page.waitForTimeout(1500);
await shot('30-protected-after-action-access');

await page.goto(`${BASE}/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV`, {
  waitUntil: 'domcontentloaded',
  timeout: 60_000,
});
await page.waitForTimeout(1500);
await shot('30-protected-replay-access');

// Logout → unauthenticated
await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=logout-button]', { timeout: 60_000 });
await page.getByTestId('logout-button').click();
await page.waitForSelector('[data-testid=sign-in-page]', { timeout: 60_000 });
await shot('30-logout-unauthenticated');

// Access denied framing (unauthenticated attempting protected route)
await page.goto(`${BASE}/scenarios`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=sign-in-page]', { timeout: 60_000 });
await shot('30-access-denied-redirect-sign-in');

// Narrow responsive
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}/sign-in`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=sign-in-page]', { timeout: 60_000 });
await shot('30-narrow-responsive-sign-in');
await page.getByTestId('dev-login-operator').click();
await page.waitForSelector('[data-testid=operator-identity]', { timeout: 60_000 });
await shot('30-narrow-responsive-authenticated');

// Short motion recording: login → identity → logout
await page.setViewportSize({ width: 1440, height: 900 });
await context.clearCookies();
await page.goto(`${BASE}/sign-in`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForSelector('[data-testid=sign-in-page]', { timeout: 60_000 });
await page.waitForSelector('[data-testid=dev-login-operator]', { timeout: 60_000 });
await page.waitForTimeout(400);
await page.getByTestId('dev-login-operator').click();
await page.waitForSelector('[data-testid=operator-identity]', { timeout: 60_000 });
await page.waitForTimeout(800);
await page.getByTestId('logout-button').click();
await page.waitForSelector('[data-testid=sign-in-page]', { timeout: 60_000 });
await page.waitForTimeout(600);

const video = page.video();
await context.close();
await browser.close();
if (video) {
  const videoPath = await video.path();
  copyFileSync(videoPath, `${EVIDENCE}/30-auth-login-logout.webm`);
  copyFileSync(videoPath, `${ARTIFACTS}/30-auth-login-logout.webm`);
  console.log(`wrote ${EVIDENCE}/30-auth-login-logout.webm`);
}
console.log('Phase 30 capture complete');
