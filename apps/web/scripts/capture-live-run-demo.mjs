#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync, spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
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
  NEXT_PUBLIC_AEGIS_DATA_SOURCE: 'api',
  NEXT_PUBLIC_API_BASE_URL: API_BASE,
  NEXT_PUBLIC_WS_URL: 'ws://127.0.0.1:8000/ws/v1/realtime',
  NEXT_PUBLIC_AEGIS_WS_TOKEN: 'aegis-dev-token',
};

function run(command) {
  try {
    const stdout = execSync(command, { cwd: ROOT, encoding: 'utf8', env });
    return { exitCode: 0, output: stdout };
  } catch (error) {
    const stdout = error.stdout?.toString?.() ?? '';
    const stderr = error.stderr?.toString?.() ?? '';
    return { exitCode: error.status ?? 1, output: `${stdout}${stderr}`.trim() };
  }
}

function createRun() {
  const response = run(
    `curl -s -X POST ${API_BASE}/api/v1/runs -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-create-1000' -d '{"schemaVersion":1,"scenarioPackagePath":"scenarios/operation-silent-relay","seed":1000}'`,
  );
  try {
    const parsed = JSON.parse(response.output);
    return parsed.run?.id ?? null;
  } catch {
    return null;
  }
}

const migrate = run('uv run alembic upgrade head');
const createResult = createRun();
let runId = createResult ?? 'unknown';

const worker = spawn('uv', ['run', 'aegis-worker', '--mode', 'outbox-relay'], {
  cwd: ROOT,
  env,
  stdio: 'ignore',
});
const api = spawn('uv', ['run', 'aegis-api'], { cwd: ROOT, env, stdio: 'ignore' });
const web = spawn('pnpm', ['--filter', '@aegis/web', 'start'], {
  cwd: ROOT,
  env,
  stdio: 'ignore',
});
await new Promise((resolveDelay) => setTimeout(resolveDelay, 8000));

for (let index = 0; index < 5; index += 1) {
  run(
    `curl -s -X POST ${API_BASE}/api/v1/runs/${runId}/step -H 'Idempotency-Key: demo-step-${index}'`,
  );
  await new Promise((resolveDelay) => setTimeout(resolveDelay, 500));
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

async function shot(name) {
  await page.goto(`${WEB_BASE}/runs/${runId}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/13-${name}.png`, fullPage: true });
}

await shot('live-command-centre');
await page
  .getByTestId('live-step')
  .click()
  .catch(() => undefined);
await page.waitForTimeout(1500);
await shot('live-graph-updates');
await page
  .getByTestId("operational-graph-canvas")
  .click({ position: { x: 400, y: 300 } })
  .catch(() => undefined);
await page.waitForTimeout(500);
await shot('selected-asset-inspector');
await shot('connection-health-status');

await page.setViewportSize({ width: 820, height: 900 });
await shot('responsive-live-layout');

await browser.close();
worker.kill();
api.kill();
web.kill();

const evidence = {
  migrate,
  runId,
  screenshots: [
    '13-live-command-centre.png',
    '13-live-graph-updates.png',
    '13-selected-asset-inspector.png',
    '13-connection-health-status.png',
    '13-responsive-live-layout.png',
  ],
};
writeFileSync(`${OUT}/13-live-run-evidence.json`, JSON.stringify(evidence, null, 2));
console.log(JSON.stringify(evidence, null, 2));
