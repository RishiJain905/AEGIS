#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const OUT = '/opt/cursor/artifacts/screenshots';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const DEFAULT_RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const STRESS_RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAW';

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

async function shot(name, fn) {
  await fn();
  await page.waitForTimeout(1000);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: name.includes('command-centre') });
  console.log(`wrote ${path}`);
}

async function waitForLayout() {
  await page.waitForSelector(
    '[data-testid=operational-graph-view][data-layout-status=complete], [data-testid=operational-graph-view][data-layout-status=running], [data-testid=operational-graph-view][data-layout-status=idle]',
    {
      timeout: 60000,
    },
  );
}

await page.goto(`${BASE}${DEFAULT_RUN}`, { waitUntil: 'load' });
await page.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 30000 });
await waitForLayout();

await shot('07-desktop-command-centre-graph', async () => {});

await page.goto(`${BASE}${STRESS_RUN}`, { waitUntil: 'load' });
await page.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 30000 });
await waitForLayout();

await shot('07-large-stress-graph', async () => {});

await shot('07-cluster-collapsed-lod', async () => {
  await page.getByTestId('graph-collapse-clusters').click();
});

await shot('07-expanded-cluster-region', async () => {
  await page.getByTestId('graph-collapse-clusters').click();
});

await page.goto(`${BASE}${DEFAULT_RUN}`, { waitUntil: 'load' });
await waitForLayout();

await shot('07-selected-node-inspector-post-layout', async () => {
  await page.getByTestId('graph-entity-asset:svc-api-gateway').click();
  await page.waitForSelector('[data-testid=graph-entity-inspector]');
});

await page.setViewportSize({ width: 768, height: 900 });
await shot('07-responsive-graph', async () => {
  await page.goto(`${BASE}${DEFAULT_RUN}`, { waitUntil: 'load' });
  await page.waitForSelector('[data-testid=operational-graph-canvas]');
});

await browser.close();
