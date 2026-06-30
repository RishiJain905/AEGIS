import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const OUT = '/opt/cursor/artifacts/screenshots';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const RUN = '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const INCIDENT = `/incidents/${encodeURIComponent('incident:inc_synthetic_001')}`;

mkdirSync(OUT, { recursive: true });

const shots = [
  { name: '01-desktop-command-centre', url: RUN, fullPage: true },
  { name: '02-operations-rail', url: RUN, selector: '[data-testid=operations-rail]' },
  { name: '03-visualization-placeholder', url: RUN, selector: '[data-testid=visualization-slot]' },
  { name: '03b-graph-domain-harness', url: RUN, selector: '[data-testid=graph-domain-harness]' },
  { name: '04-inspector-panel', url: INCIDENT, selector: '[data-testid=inspector-panel]' },
  { name: '05-timeline-area', url: RUN, selector: '[data-testid=timeline-area]' },
  { name: '06-responsive-layout', url: RUN, fullPage: true, viewport: { width: 768, height: 900 } },
  { name: '07-offline-state', url: `${RUN}?profile=offline`, fullPage: true },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

for (const shot of shots) {
  if (shot.viewport) {
    await page.setViewportSize(shot.viewport);
  } else {
    await page.setViewportSize({ width: 1440, height: 900 });
  }
  await page.goto(`${BASE}${shot.url}`, { waitUntil: 'networkidle' });
  const filePath = `${OUT}/${shot.name}.png`;
  if (shot.selector) {
    await page.locator(shot.selector).screenshot({ path: filePath });
  } else {
    await page.screenshot({ path: filePath, fullPage: shot.fullPage });
  }
  console.log(`wrote ${filePath}`);
}

await browser.close();
