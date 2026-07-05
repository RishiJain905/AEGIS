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
const API_BASE = process.env.SCREENSHOT_API_URL ?? 'http://127.0.0.1:8000';
const SYNTHETIC_INCIDENT_ID = encodeURIComponent('incident:inc_synthetic_001');
const HYPOTHESIS_ONE_ID = 'hyp_01ARZ3NDEKTSV4RRFFQ69G5FB2';
const HYPOTHESIS_TWO_ID = 'hyp_01ARZ3NDEKTSV4RRFFQ69G5FB3';

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
  AEGIS_PROVIDER_DEFAULT: 'mock',
  AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS: 'true',
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

const oracleTests = run('uv run pytest tests/agents/oracle -q');
const oracleHarness = run('PYTHONPATH=. uv run python scripts/run_oracle_harness.py');

const api = spawn('uv', ['run', 'aegis-api'], { cwd: ROOT, env, stdio: 'ignore' });
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

await waitForUrl(`${API_BASE}/health`);
await waitForUrl(`${WEB_BASE}/scenarios`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

async function shot(name, url, fn = async () => {}) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await fn();
  await page.waitForTimeout(1200);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  console.log(`wrote ${path}`);
  return path;
}

const paths = [];

paths.push(
  await shot('01-silent-relay-running', `${WEB_BASE}/scenarios`, async () => {
    await page.waitForSelector('[data-testid="scenarios-table"]', { timeout: 30000 });
    await page.getByText('Operation Silent Relay').waitFor({ timeout: 30000 });
  }),
);

paths.push(
  await shot('02-investigation-evidence', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-panel"]', { timeout: 30000 });
    await page.waitForSelector('[data-testid="investigation-evidence-panel"]', { timeout: 30000 });
    await page.waitForSelector('[data-testid="investigation-triage-panel"]', { timeout: 30000 });
  }),
);

paths.push(
  await shot('03-oracle-multiple-hypotheses', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-hypotheses-panel"]', { timeout: 30000 });
    await page.waitForSelector(`[data-testid="hypothesis-card-${HYPOTHESIS_ONE_ID}"]`, {
      timeout: 30000,
    });
    await page.waitForSelector(`[data-testid="hypothesis-card-${HYPOTHESIS_TWO_ID}"]`, {
      timeout: 30000,
    });
  }),
);

paths.push(
  await shot('04-hypothesis-detail-provenance', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector(`[data-testid="hypothesis-detail-${HYPOTHESIS_ONE_ID}"]`, {
      timeout: 30000,
    });
    await page.click(`[data-testid="hypothesis-card-${HYPOTHESIS_ONE_ID}"]`);
    await page.waitForTimeout(500);
  }),
);

paths.push(
  await shot('05-confidence-uncertainty', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector(`[data-testid="hypothesis-detail-${HYPOTHESIS_ONE_ID}"]`, {
      timeout: 30000,
    });
    await page.getByText('Unknowns').scrollIntoViewIfNeeded();
  }),
);

paths.push(
  await shot('06-contradictions-visible', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-contradictions-panel"]', {
      timeout: 30000,
    });
    await page.click(`[data-testid="hypothesis-card-${HYPOTHESIS_TWO_ID}"]`);
    await page.waitForSelector(`[data-testid="hypothesis-detail-${HYPOTHESIS_TWO_ID}"]`, {
      timeout: 30000,
    });
    await page.getByText('Contradicting evidence').scrollIntoViewIfNeeded();
  }),
);

paths.push(
  await shot('07-invalid-output-rejected', `${API_BASE}/agents/observability`, async () => {
    await page.waitForSelector('#oracle-observability', { timeout: 30000 });
    await page.click('button:has-text("Show invalid ORACLE output rejection")');
    await page.waitForTimeout(1500);
  }),
);

paths.push(
  await shot('08-hypothesis-revision', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.click(`[data-testid="hypothesis-card-${HYPOTHESIS_TWO_ID}"]`);
    await page.waitForSelector(`[data-testid="hypothesis-detail-${HYPOTHESIS_TWO_ID}"]`, {
      timeout: 30000,
    });
    await page.getByText('Revision history').click();
    await page.waitForTimeout(500);
  }),
);

paths.push(
  await shot('09-agent-lifecycle-audit', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-agent-lifecycle-panel"]', {
      timeout: 30000,
    });
  }),
);

paths.push(
  await shot('10-mock-deterministic', `${API_BASE}/agents/observability`, async () => {
    await page.waitForSelector('#oracle-observability', { timeout: 30000 });
    await page.click('button:has-text("Trigger ORACLE for harness run")');
    await page.waitForTimeout(3000);
  }),
);

paths.push(
  await shot('11-realtime-update', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-hypotheses-panel"]', { timeout: 30000 });
    await page.waitForSelector('[data-testid="hypothesis-comparison-hcmp_synthetic_001"]', {
      timeout: 30000,
    });
  }),
);

const narrow = await browser.newPage({ viewport: { width: 390, height: 844 } });
paths.push(
  await (async () => {
    await narrow.goto(`${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, {
      waitUntil: 'domcontentloaded',
      timeout: 90000,
    });
    await narrow.waitForSelector('[data-testid="investigation-hypotheses-panel"]', { timeout: 30000 });
    await narrow.waitForTimeout(1200);
    const path = `${OUT}/12-responsive-hypotheses.png`;
    await narrow.screenshot({ path, fullPage: true });
    console.log(`wrote ${path}`);
    return path;
  })(),
);
await narrow.close();

paths.push(
  await shot('21-oracle-ci-evidence', `${API_BASE}/agents/observability`, async () => {
    await page.evaluate(
      ({ oracleOutput, harnessOutput }) => {
        const el = document.getElementById('ci-evidence');
        if (el) {
          el.textContent = `${oracleOutput}\n\n${harnessOutput}`;
        }
      },
      {
        oracleOutput: oracleTests.output,
        harnessOutput: oracleHarness.output.slice(0, 1200),
      },
    );
  }),
);

writeFileSync(
  `${OUT}/21-oracle-demo-summary.json`,
  JSON.stringify({ paths, oracleTests, oracleHarness }, null, 2),
);

await browser.close();
api.kill('SIGTERM');
web.kill('SIGTERM');

console.log(JSON.stringify({ paths }, null, 2));
