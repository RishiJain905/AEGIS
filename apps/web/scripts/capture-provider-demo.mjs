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

const conformance = run('uv run pytest tests/agents/provider-conformance -q');
const harness = run('uv run python scripts/run_provider_harness.py');

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
  await shot('18-command-centre', `${WEB_BASE}/scenarios`, async () => {
    await page.waitForTimeout(800);
  }),
);

paths.push(
  await shot('18-provider-harness', `${API_BASE}/providers/observability`, async () => {
    await page.waitForSelector('#config', { timeout: 30000 });
  }),
);

await page.goto(`${API_BASE}/providers/observability`, { waitUntil: 'domcontentloaded' });
await page.click('button:has-text("Run mock structured output")');
await page.waitForTimeout(1500);
paths.push(
  await shot('18-mock-provider-success', `${API_BASE}/providers/observability`, async () => {
    await page.click('button:has-text("Run mock structured output")');
    await page.waitForTimeout(1200);
  }),
);

await page.goto(`${API_BASE}/providers/observability`, { waitUntil: 'domcontentloaded' });
await page.click('button:has-text("Replay recorded fixture")');
await page.waitForTimeout(1500);
paths.push(
  await shot('18-recorded-replay', `${API_BASE}/providers/observability`, async () => {
    await page.click('button:has-text("Replay recorded fixture")');
    await page.waitForTimeout(1200);
  }),
);

await page.goto(`${API_BASE}/providers/observability`, { waitUntil: 'domcontentloaded' });
await page.click('button:has-text("Run mock structured output")');
await page.waitForTimeout(1200);
paths.push(await shot('18-response-metadata', `${API_BASE}/providers/observability`));

await page.goto(`${API_BASE}/providers/observability`, { waitUntil: 'domcontentloaded' });
await page.click('button:has-text("Valid structured output")');
await page.waitForTimeout(1200);
paths.push(await shot('18-structured-output-valid', `${API_BASE}/providers/observability`));

await page.goto(`${API_BASE}/providers/observability`, { waitUntil: 'domcontentloaded' });
await page.click('button:has-text("Reject malformed output")');
await page.waitForTimeout(1200);
paths.push(await shot('18-structured-output-rejected', `${API_BASE}/providers/observability`));

await page.goto(`${API_BASE}/providers/observability`, { waitUntil: 'domcontentloaded' });
await page.click('button:has-text("Unsupported capability")');
await page.waitForTimeout(1200);
paths.push(await shot('18-normalized-error', `${API_BASE}/providers/observability`));

await page.goto(`${API_BASE}/providers/observability`, { waitUntil: 'domcontentloaded' });
await page.click('button:has-text("Missing credentials")');
await page.waitForTimeout(1200);
paths.push(await shot('18-missing-credentials', `${API_BASE}/providers/observability`));

paths.push(
  await shot('18-ci-no-external-inference', `${API_BASE}/providers/observability`, async () => {
    await page.evaluate(
      ({ conformanceOutput, harnessOutput }) => {
        const el = document.getElementById('ci-evidence');
        if (el) {
          el.textContent = `${conformanceOutput}\n\n${harnessOutput}`;
        }
      },
      { conformanceOutput: conformance.output, harnessOutput: harness.output.slice(0, 1200) },
    );
  }),
);

writeFileSync(
  `${OUT}/18-provider-demo-summary.json`,
  JSON.stringify({ paths, conformance, harness }, null, 2),
);

await browser.close();
api.kill('SIGTERM');
web.kill('SIGTERM');

console.log(JSON.stringify({ paths }, null, 2));
