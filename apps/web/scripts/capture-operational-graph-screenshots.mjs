import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const OUT = '/opt/cursor/artifacts/screenshots';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

async function shot(name, fn) {
  await fn();
  await page.waitForTimeout(500);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: name.includes('command-centre') });
  console.log(`wrote ${path}`);
}

await page.goto(`${BASE}${RUN}`, { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 30000 });

await shot('06-desktop-command-centre-graph', async () => {});

await shot('06-selected-node-inspector', async () => {
  await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
  await page.waitForSelector('[data-testid=graph-entity-inspector]');
});

await shot('06-neighborhood-isolation', async () => {
  await page.getByTestId('graph-isolate-neighborhood').click();
});

await shot('06-path-highlight', async () => {
  await page.getByTestId('graph-restore-full').click();
  await page.getByTestId('graph-path-mode').click();
  await page.getByTestId('graph-entity-asset:device-workstation-01').click();
  await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
  await page.waitForSelector('[data-testid=path-inspector-section]');
});

await shot('06-search-filter', async () => {
  await page.getByTestId('graph-search-input').fill('Gateway');
});

await shot('06-risk-overlay', async () => {
  await page.getByTestId('graph-search-input').fill('');
  await page.getByTestId('graph-overlay-risk').click();
  await page.getByTestId('graph-overlay-status').click();
});

await page.setViewportSize({ width: 768, height: 900 });
await shot('06-responsive-graph', async () => {
  await page.goto(`${BASE}${RUN}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid=operational-graph-canvas]');
});

await browser.close();
