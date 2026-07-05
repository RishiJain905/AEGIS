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

const investigationTests = run('uv run pytest tests/agents -q -k "watchtower or trace"');
const runtimeHarness = run('uv run python scripts/run_agent_runtime_harness.py');

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
  await shot('20-incident-investigation-panel', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-panel"]', { timeout: 30000 });
    await page.waitForSelector('[data-testid="investigation-triage-panel"]', { timeout: 30000 });
  }),
);

paths.push(
  await shot('20-investigation-evidence', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-evidence-panel"]', { timeout: 30000 });
    await page.waitForSelector('[data-testid="investigation-contradictions-panel"]', { timeout: 30000 });
  }),
);

paths.push(
  await shot('20-investigation-agent-lifecycle', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="investigation-agent-lifecycle-panel"]', { timeout: 30000 });
  }),
);

paths.push(
  await shot('20-investigation-graph-overlay', `${WEB_BASE}/incidents/${SYNTHETIC_INCIDENT_ID}`, async () => {
    await page.waitForSelector('[data-testid="operational-graph-view"]', { timeout: 30000 });
    await page.waitForSelector('[data-testid="investigation-overlay-panel"]', { timeout: 30000 });
    await page.click('[data-testid="highlight-investigation-overlay"]');
    await page.waitForTimeout(800);
  }),
);

paths.push(
  await shot('20-watchtower-observability', `${API_BASE}/agents/observability`, async () => {
    await page.waitForSelector('#watchtower-trace', { timeout: 30000 });
    await page.click('button:has-text("Trigger WATCHTOWER for harness run")');
    await page.waitForTimeout(2500);
  }),
);

paths.push(
  await shot('20-investigation-detail-api', `${API_BASE}/agents/observability`, async () => {
    await page.click('button:has-text("Show investigation detail")');
    await page.waitForTimeout(1500);
  }),
);

paths.push(
  await shot('20-trace-session-detail', `${API_BASE}/agents/observability`, async () => {
    await page.click('button:has-text("Load TRACE session detail")');
    await page.waitForTimeout(1500);
  }),
);

paths.push(
  await shot('20-ci-investigation-evidence', `${API_BASE}/agents/observability`, async () => {
    await page.evaluate(
      ({ investigationOutput, harnessOutput }) => {
        const el = document.getElementById('ci-evidence');
        if (el) {
          el.textContent = `${investigationOutput}\n\n${harnessOutput}`;
        }
      },
      {
        investigationOutput: investigationTests.output,
        harnessOutput: runtimeHarness.output.slice(0, 1200),
      },
    );
  }),
);

writeFileSync(
  `${OUT}/20-watchtower-trace-demo-summary.json`,
  JSON.stringify({ paths, investigationTests, runtimeHarness }, null, 2),
);

await browser.close();
api.kill('SIGTERM');
web.kill('SIGTERM');

console.log(JSON.stringify({ paths }, null, 2));
