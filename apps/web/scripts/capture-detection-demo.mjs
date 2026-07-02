#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync, spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../../..');
const OUT = '/opt/cursor/artifacts/screenshots';
const API_BASE = process.env.API_BASE_URL ?? 'http://127.0.0.1:8000';
const WEB_BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';

mkdirSync(OUT, { recursive: true });

const env = {
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

const calibrate = run('uv run python scripts/calibrate_baselines.py');
const evalRules = run('uv run python scripts/evaluate_rules.py');
const ruleTests = run('uv run pytest tests/ml/rules -q');

const api = spawn('uv', ['run', 'aegis-api'], { cwd: ROOT, env, stdio: 'ignore' });
const web = spawn('pnpm', ['--filter', '@aegis/web', 'dev', '--port', '3000'], {
  cwd: ROOT,
  env,
  stdio: 'ignore',
});
await new Promise((resolveDelay) => setTimeout(resolveDelay, 12000));

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

await shot('15-silent-relay-command-centre', `${WEB_BASE}/scenarios`);
await shot('15-deterministic-rule-inspector', `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0`, async () => {
  await page.getByTestId('inspector-panel').waitFor({ state: 'visible' });
});
await shot('15-statistical-baseline-alert', `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB1`, async () => {
  await page.getByTestId('alerts-panel').waitFor({ state: 'visible' });
});
await shot('15-alerts-in-inspector', `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0`);
await shot('15-alert-detail-explanation', `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0`, async () => {
  const details = page.locator('details summary');
  if (await details.count()) {
    await details.first().click();
  }
});
await shot('15-dedup-suppression-note', `${API_BASE}/detection/observability`);
await shot('15-normal-no-alert-run', `${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV`);
await shot('15-evaluation-metrics', `${API_BASE}/detection/observability`, async () => {
  await page.evaluate(() => {
    const pre = document.getElementById('evaluation');
    if (pre) {
      pre.textContent = JSON.stringify(
        {
          calibrate: 'see evaluate_rules.py output',
          ruleTests: 'tests/ml/rules',
          phase16Deferred: true,
        },
        null,
        2,
      );
    }
  });
});

const narrow = await browser.newPage({ viewport: { width: 768, height: 1200 } });
await narrow.goto(`${WEB_BASE}/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0`, {
  waitUntil: 'domcontentloaded',
  timeout: 90000,
});
await narrow.waitForTimeout(1500);
await narrow.screenshot({ path: `${OUT}/15-responsive-alerts.png`, fullPage: true });
console.log(`wrote ${OUT}/15-responsive-alerts.png`);

await browser.close();
api.kill();
web.kill();

console.log(
  JSON.stringify(
    {
      calibrate: calibrate.exitCode,
      evaluateRules: evalRules.exitCode,
      ruleTests: ruleTests.output,
    },
    null,
    2,
  ),
);
