#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync, spawn } from 'node:child_process';
import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../../..');
const OUT = '/opt/cursor/artifacts/screenshots';
const WEB_BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

mkdirSync(OUT, { recursive: true });

function loadEnvExample() {
  const parsed = {};
  const raw = readFileSync(resolve(ROOT, '.env.example'), 'utf8');
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const [key, ...rest] = trimmed.split('=');
    parsed[key] = rest.join('=');
  }
  return parsed;
}

const env = {
  ...loadEnvExample(),
  ...process.env,
  PATH: `${process.env.HOME}/.local/bin:${process.env.PATH}`,
  NEXT_PUBLIC_AEGIS_DATA_SOURCE: process.env.NEXT_PUBLIC_AEGIS_DATA_SOURCE ?? 'fixture',
};

function run(command) {
  try {
    return { exitCode: 0, output: execSync(command, { cwd: ROOT, encoding: 'utf8', env }) };
  } catch (error) {
    return {
      exitCode: error.status ?? 1,
      output: `${error.stdout?.toString?.() ?? ''}${error.stderr?.toString?.() ?? ''}`.trim(),
    };
  }
}

const riskTests = run('uv run pytest tests/ml/risk -q');
const web = spawn('pnpm', ['--filter', '@aegis/web', 'dev', '--port', '3000'], {
  cwd: ROOT,
  env,
  stdio: 'ignore',
});

async function waitForUrl(url, attempts = 60) {
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

async function selectGraphEntity(page, assetId) {
  await page.getByTestId(`graph-entity-${assetId}`).click();
  await page.waitForTimeout(400);
}

await waitForUrl(`${WEB_BASE}/scenarios`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

async function shot(name, url, fn = async () => {}) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await fn();
  await page.waitForTimeout(1500);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  console.log(`wrote ${path}`);
  return path;
}

const runUrl = `${WEB_BASE}/runs/${RUN_ID}`;
const paths = [];

paths.push(
  await shot('17-silent-relay-command-centre', runUrl, async () => {
    await page.getByTestId('operational-graph-canvas').waitFor({ timeout: 30000 });
  }),
);

paths.push(
  await shot('17-detection-signal-origin', runUrl, async () => {
    await page.getByTestId('alerts-panel').waitFor({ timeout: 30000 });
    await selectGraphEntity(page, 'asset:svc-logistics-api');
  }),
);

paths.push(
  await shot('17-risk-propagation-graph', runUrl, async () => {
    await page.getByTestId('operational-graph-canvas').waitFor({ timeout: 30000 });
  }),
);

paths.push(
  await shot('17-selected-asset-risk-explanation', runUrl, async () => {
    await page.getByTestId('graph-entity-list').waitFor({ timeout: 30000 });
    await selectGraphEntity(page, 'asset:db-customer-records');
    await page.getByTestId('risk-explanation-panel').waitFor({ timeout: 10000 });
    await page.getByTestId('risk-propagated-score').waitFor({ timeout: 10000 });
  }),
);

paths.push(
  await shot('17-highlighted-risk-path', runUrl, async () => {
    await selectGraphEntity(page, 'asset:db-customer-records');
    await page.getByTestId('highlight-risk-path').waitFor({ timeout: 10000 });
    await page.getByTestId('highlight-risk-path').click();
    await page.getByTestId('path-inspector-section').waitFor({ timeout: 10000 });
  }),
);

paths.push(
  await shot('17-direct-vs-propagated-comparison', runUrl, async () => {
    await selectGraphEntity(page, 'asset:svc-logistics-api');
    await page.getByTestId('risk-comparison').waitFor({ timeout: 10000 });
  }),
);

const narrow = await browser.newPage({ viewport: { width: 768, height: 1024 } });
await narrow.goto(runUrl, { waitUntil: 'domcontentloaded' });
await narrow.getByTestId('graph-entity-list').waitFor({ timeout: 30000 });
await narrow.getByTestId('graph-entity-asset:db-customer-records').click();
await narrow.waitForTimeout(1500);
const narrowPath = `${OUT}/17-responsive-risk-layout.png`;
await narrow.screenshot({ path: narrowPath, fullPage: true });
console.log(`wrote ${narrowPath}`);
paths.push(narrowPath);

paths.push(
  await shot('17-risk-validation-output', runUrl, async () => {
    await page.evaluate((output) => {
      const el = document.createElement('pre');
      el.id = 'risk-validation-output';
      el.textContent = output;
      el.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;background:#111;color:#0f0;padding:8px;font-size:11px;z-index:9999';
      document.body.appendChild(el);
    }, riskTests.output);
  }),
);

await browser.close();
await narrow.close();
web.kill('SIGTERM');

console.log(JSON.stringify({ paths, riskTests: riskTests.output }, null, 2));
