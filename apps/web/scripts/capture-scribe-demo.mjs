#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync, spawn } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../../..');
const OUT = '/opt/cursor/artifacts/screenshots';
const WEB_BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const SYNTHETIC_INCIDENT_ID = encodeURIComponent('incident:inc_synthetic_001');
const SYNTHETIC_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

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
  NEXT_PUBLIC_AEGIS_DATA_SOURCE: 'fixture',
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

const scribeTests = run('uv run pytest tests/reports tests/agents/scribe -q');
const scribeHarness = run('PYTHONPATH=. uv run python scripts/run_scribe_harness.py');

const web = spawn('pnpm', ['--filter', '@aegis/web', 'dev', '--port', '3000'], {
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

async function shot(name, url, fn = async () => {}) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await fn();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

await shot('01-silent-relay-running', `${WEB_BASE}/runs/${SYNTHETIC_RUN_ID}`);
await shot(
  '02-oracle-hypotheses-evidence',
  `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
  async () => {
    await page.waitForSelector('[data-testid="investigation-panel"]', { timeout: 30000 });
  },
);
await shot(
  '03-bastion-warden-proposal-state',
  `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
  async () => {
    await page.waitForSelector('[data-testid^="proposal-card-"]', { timeout: 30000 });
  },
);
await shot('04-scribe-report-summary', `${WEB_BASE}/reports`, async () => {
  await page.waitForSelector('[data-testid="reports-panel"]', { timeout: 30000 });
});
await shot('05-scribe-timeline', `${WEB_BASE}/reports`, async () => {
  await page.waitForSelector('[data-testid^="report-timeline-"]', { timeout: 30000 });
});
await shot('06-scribe-claim-provenance', `${WEB_BASE}/reports`, async () => {
  await page.waitForSelector('[data-testid="report-claim-claim_002"]', { timeout: 30000 });
});
await shot('07-scribe-claim-categories', `${WEB_BASE}/reports`, async () => {
  await page.waitForSelector('[data-claim-kind="unsupported"]', { timeout: 30000 });
});
await shot('08-scribe-export-metadata', `${WEB_BASE}/reports`, async () => {
  await page.waitForSelector('code', { timeout: 30000 });
});
await shot('09-scribe-agent-audit', `${WEB_BASE}/reports`, async () => {
  await page.waitForSelector('text=agent-session:ags_scribe_001', { timeout: 30000 });
});
await shot('10-scribe-validation-evidence', `${WEB_BASE}/reports`, async () => {
  await page.evaluate(
    ({ scribeTestsOutput, scribeHarnessOutput }) => {
      const el = document.querySelector('[data-testid="reports-panel"]');
      if (el) {
        el.setAttribute('data-validation', `${scribeTestsOutput}\n${scribeHarnessOutput}`);
      }
    },
    {
      scribeTestsOutput: scribeTests.output.slice(0, 500),
      scribeHarnessOutput: scribeHarness.output.slice(0, 500),
    },
  );
});
await shot('11-scribe-realtime-update', `${WEB_BASE}/reports`);
await page.setViewportSize({ width: 390, height: 900 });
await shot('12-scribe-responsive', `${WEB_BASE}/reports`, async () => {
  await page.waitForSelector('[data-testid="reports-panel"]', { timeout: 30000 });
});

writeFileSync(
  `${OUT}/23-scribe-demo-summary.json`,
  JSON.stringify({ scribeTests, scribeHarness, outputDir: OUT }, null, 2),
);

web.kill();
await browser.close();
