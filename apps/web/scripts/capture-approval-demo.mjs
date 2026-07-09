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
const PROPOSAL_ONE_ID = 'prp_01ARZ3NDEKTSV4RRFFQ69G5FB9';
const PROPOSAL_TWO_ID = 'prp_01ARZ3NDEKTSV4RRFFQ69G5FBA';

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

const approvalUnit = run('uv run pytest tests/approvals -q');
const approvalIntegration = run(
  'AEGIS_INTEGRATION_POSTGRES=1 uv run pytest tests/integration/approvals -q',
);

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
  await shot(
    '02-proposal-requiring-approval',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.waitForSelector('[data-testid="proposals-panel"]', { timeout: 30000 });
      await page.waitForSelector(`[data-testid="proposal-card-${PROPOSAL_ONE_ID}"]`, {
        timeout: 30000,
      });
      await page.getByText('approval_required').first().scrollIntoViewIfNeeded();
    },
  ),
);

paths.push(
  await shot(
    '03-proposal-inspection-fields',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.click(`[data-testid="proposal-card-${PROPOSAL_ONE_ID}"]`);
      await page
        .locator(`[data-testid="proposal-card-${PROPOSAL_ONE_ID}"]`)
        .getByText('Expected consequences')
        .scrollIntoViewIfNeeded();
    },
  ),
);

paths.push(
  await shot(
    '04-warden-result-approval-required',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.waitForSelector(`[data-testid="policy-result-${PROPOSAL_ONE_ID}"]`, {
        timeout: 30000,
      });
      await page
        .locator(`[data-testid="approval-controls-${PROPOSAL_ONE_ID}"]`)
        .scrollIntoViewIfNeeded();
    },
  ),
);

paths.push(
  await shot(
    '05-approval-controls-ready',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.waitForSelector(`[data-testid="approval-controls-${PROPOSAL_ONE_ID}"]`, {
        timeout: 30000,
      });
      await page
        .getByText('Human approval required — decisions are enforced by the backend')
        .scrollIntoViewIfNeeded();
    },
  ),
);

paths.push(
  await shot(
    '06-modify-revision-form',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.click(`[data-testid="modify-proposal-details-${PROPOSAL_ONE_ID}"] summary`);
      await page
        .locator(`[data-testid="modify-rationale-${PROPOSAL_ONE_ID}"]`)
        .scrollIntoViewIfNeeded();
    },
  ),
);

paths.push(
  await shot(
    '07-reject-path-controls',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.fill(
        `[data-testid="reject-reason-${PROPOSAL_ONE_ID}"]`,
        'Collateral risk too high for current window',
      );
      await page
        .locator(`[data-testid="reject-proposal-${PROPOSAL_ONE_ID}"]`)
        .scrollIntoViewIfNeeded();
    },
  ),
);

paths.push(
  await shot(
    '08-audit-approvals-executed',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.waitForSelector('[data-testid="proposal-lifecycle-panel"]', { timeout: 30000 });
      await page.getByText('approval ').first().scrollIntoViewIfNeeded();
    },
  ),
);

paths.push(
  await shot(
    '09-allow-proposal-without-approval-controls',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.click(`[data-testid="proposal-card-${PROPOSAL_TWO_ID}"]`);
      await page.waitForSelector(`[data-testid="policy-result-${PROPOSAL_TWO_ID}"]`, {
        timeout: 30000,
      });
    },
  ),
);

paths.push(
  await shot(
    '10-realtime-investigation-surface',
    `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`,
    async () => {
      await page.waitForSelector('[data-testid="proposals-panel"]', { timeout: 30000 });
      await page.waitForSelector(`[data-testid="approval-controls-${PROPOSAL_ONE_ID}"]`, {
        timeout: 30000,
      });
    },
  ),
);

const narrow = await browser.newPage({ viewport: { width: 390, height: 844 } });
paths.push(
  await (async () => {
    await narrow.goto(`${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, {
      waitUntil: 'domcontentloaded',
      timeout: 90000,
    });
    await narrow.waitForSelector(`[data-testid="approval-controls-${PROPOSAL_ONE_ID}"]`, {
      timeout: 30000,
    });
    await narrow.waitForTimeout(1200);
    const path = `${OUT}/11-responsive-approval-controls.png`;
    await narrow.screenshot({ path, fullPage: true });
    console.log(`wrote ${path}`);
    return path;
  })(),
);
await narrow.close();

paths.push(
  await shot('12-phase24-ci-evidence', `${API_BASE}/agents/observability`, async () => {
    await page.evaluate(
      ({ unitOutput, integrationOutput }) => {
        const el = document.getElementById('ci-evidence');
        if (el) {
          el.textContent = `Phase 24 approval unit tests:\n${unitOutput}\n\nPhase 24 approval integration:\n${integrationOutput}`;
        }
      },
      {
        unitOutput: approvalUnit.output.slice(0, 2000),
        integrationOutput: approvalIntegration.output.slice(0, 2000),
      },
    );
  }),
);

writeFileSync(
  `${OUT}/24-approval-workflow-demo-summary.json`,
  JSON.stringify({ paths, approvalUnit, approvalIntegration }, null, 2),
);

await browser.close();
api.kill('SIGTERM');
web.kill('SIGTERM');

console.log(JSON.stringify({ paths, approvalUnit, approvalIntegration }, null, 2));
