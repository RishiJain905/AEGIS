#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync, spawn } from 'node:child_process';
import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../../..');
const OUT = '/opt/cursor/artifacts/screenshots';
const API_BASE = process.env.API_BASE_URL ?? 'http://127.0.0.1:8000';
const WEB_BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';

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

const train = run('uv run python scripts/train_isolation_forest.py --steps 300');
const evalModel = run('uv run python scripts/evaluate_model.py --steps 300');
const modelTests = run('uv run pytest tests/ml/models -q');

const api = spawn('uv', ['run', 'aegis-api'], { cwd: ROOT, env, stdio: 'ignore' });
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

await waitForUrl(`${API_BASE}/health`);
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
}

await shot('16-silent-relay-command-centre', `${WEB_BASE}/scenarios`);
await shot(
  '16-isolation-forest-anomaly-inspector',
  `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB1`,
  async () => {
    await page.getByTestId('inspector-panel').waitFor({ state: 'visible' });
    const details = page.locator('details summary');
    if (await details.count()) {
      await details.first().click();
    }
  },
);
await shot(
  '16-anomaly-score-threshold-model-version',
  `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB1`,
);
await shot('16-model-vs-baseline-comparison', `${API_BASE}/models/observability`);
await shot(
  '16-evaluation-metrics-score-distribution',
  `${API_BASE}/models/observability`,
  async () => {
    await page.evaluate(async (base) => {
      const res = await fetch(`${base}/api/v1/detection/baselines`);
      window.__baseline = res.ok ? await res.json() : null;
    }, API_BASE);
  },
);
await shot('16-manifest-checksum-validation', `${API_BASE}/models/observability`, async () => {
  await page.getByRole('button', { name: 'Verify checksum + schema' }).click();
  await page.waitForTimeout(800);
});
await shot('16-corrupt-artifact-rejection', `${API_BASE}/models/observability`, async () => {
  await page.getByRole('button', { name: 'Simulate corrupt artifact' }).click();
  await page.waitForTimeout(800);
});
await shot('16-fallback-rules-only', `${API_BASE}/detection/observability`);
await shot('16-normal-below-threshold', `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0`);

const narrow = await browser.newPage({ viewport: { width: 768, height: 1200 } });
await narrow.goto(`${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB1`, {
  waitUntil: 'domcontentloaded',
  timeout: 90000,
});
await narrow.waitForTimeout(1500);
await narrow.screenshot({ path: `${OUT}/16-narrow-layout-anomaly-info.png`, fullPage: true });
console.log(`wrote ${OUT}/16-narrow-layout-anomaly-info.png`);

await browser.close();
await narrow.close();
api.kill();
web.kill();

console.log(
  JSON.stringify(
    {
      train: train.exitCode,
      evaluate: evalModel.exitCode,
      modelTests: modelTests.exitCode,
      screenshots: OUT,
    },
    null,
    2,
  ),
);
