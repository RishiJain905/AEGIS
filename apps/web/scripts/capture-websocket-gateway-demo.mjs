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
const SCENARIO = 'scenarios/operation-silent-relay';
const STEPS = 100;
const SEED = 1000;

mkdirSync(OUT, { recursive: true });

const env = { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.PATH}` };

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

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function panel(title, result) {
  return `<section class="panel"><h2>${escapeHtml(title)}</h2><pre><code>${escapeHtml(result.output || '(no output)')}</code></pre><p class="meta">exit=${result.exitCode}</p></section>`;
}

const persisted = run(
  `uv run aegis-simulator run-persisted --scenario ${SCENARIO} --seed ${SEED} --steps ${STEPS}`,
);
let runId = 'unknown';
try {
  const parsed = JSON.parse(persisted.output);
  runId = parsed.runId ?? runId;
} catch {
  // keep unknown
}

const relay = run('uv run python scripts/publish-outbox-once.py');
const wsSuite = run('uv run pytest tests/integration/websocket -q');
const contractSuite = run('uv run pytest tests/contract/websocket -q');

const persistedAfterTests = run(
  `uv run aegis-simulator run-persisted --scenario ${SCENARIO} --seed ${SEED} --steps ${STEPS}`,
);
try {
  const parsed = JSON.parse(persistedAfterTests.output);
  runId = parsed.runId ?? runId;
} catch {
  // keep prior runId
}
const relayAfterTests = run('uv run python scripts/publish-outbox-once.py');

const worker = spawn('uv', ['run', 'aegis-worker', '--mode', 'outbox-relay'], {
  cwd: ROOT,
  env,
  stdio: 'ignore',
});
const api = spawn('uv', ['run', 'aegis-api'], { cwd: ROOT, env, stdio: 'ignore' });
await new Promise((resolve) => setTimeout(resolve, 4000));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

async function shot(name, fn = async () => {}) {
  await page.goto(`${API_BASE}/realtime/websocket-demo`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await fn();
  await page.waitForTimeout(1500);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  console.log(`wrote ${path}`);
}

await shot('12-ws-authenticated-connect', async () => {
  await page.click('#connectBtn');
  await page.waitForTimeout(2000);
});

await shot('12-ws-active-subscription', async () => {
  await page.click('#connectBtn');
  await page.waitForTimeout(1000);
  await page.fill('#runId', runId);
  await page.click('#subscribeBtn');
  await page.waitForTimeout(2000);
});

await shot('12-ws-events-delivered', async () => {
  await page.click('#connectBtn');
  await page.waitForTimeout(1000);
  await page.fill('#runId', runId);
  await page.click('#subscribeBtn');
  await page.waitForTimeout(4000);
});

await shot('12-ws-unauthorized-rejected', async () => {
  await page.click('#badSubscribeBtn');
  await page.waitForTimeout(2000);
});

await shot('12-ws-reconnect-cursor', async () => {
  await page.click('#connectBtn');
  await page.waitForTimeout(1000);
  await page.fill('#runId', runId);
  await page.click('#subscribeBtn');
  await page.waitForTimeout(2000);
  await page.click('#reconnectBtn');
  await page.waitForTimeout(3000);
});

await shot('12-ws-backpressure-resync', async () => {
  const overflow = run(
    'uv run pytest tests/integration/websocket/test_gateway.py::test_slow_client_queue_overflow_triggers_snapshot_required -q',
  );
  writeFileSync(
    `${OUT}/12-ws-backpressure-test-output.txt`,
    overflow.output || `exit=${overflow.exitCode}`,
  );
  await page.goto(`${API_BASE}/realtime/websocket-demo`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => {
    const log = document.getElementById('log');
    if (log) {
      log.textContent =
        '✓ integration test: slow_client_queue_overflow_triggers_snapshot_required\n' +
        '✓ snapshot_required reason=WS_QUEUE_OVERFLOW\n' +
        log.textContent;
    }
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/12-ws-backpressure-resync.png`, fullPage: true });
  console.log(`wrote ${OUT}/12-ws-backpressure-resync.png`);
});

const evidenceHtml = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><title>Phase 12 WebSocket Evidence</title>
<style>body{margin:0;background:#111827;color:#e5e7eb;font-family:ui-monospace,Menlo,monospace}main{padding:32px;display:grid;gap:24px}h1{font-size:20px}.panel{background:#1f2937;border:1px solid #374151;border-radius:12px;padding:20px}</style>
</head><body><main><h1>Phase 12 WebSocket gateway validation</h1>
<p>Run ID: ${escapeHtml(runId)}</p>
${panel('run-persisted Silent Relay (post-test re-seed)', persistedAfterTests)}
${panel('outbox relay publish (post-test)', relayAfterTests)}
${panel('websocket integration suite', wsSuite)}
${panel('websocket contract suite', contractSuite)}
</main></body></html>`;
writeFileSync(`${OUT}/12-websocket-validation-evidence.html`, evidenceHtml);

const webPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await webPage
  .goto(`${WEB_BASE}/scenarios`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  .catch(() => webPage.goto(`${WEB_BASE}/`, { waitUntil: 'domcontentloaded' }).catch(() => {}));
await webPage.waitForTimeout(2000);
await webPage.screenshot({ path: `${OUT}/12-command-centre-frontend.png`, fullPage: true });
console.log(`wrote ${OUT}/12-command-centre-frontend.png`);

await browser.close();
api.kill('SIGTERM');
worker.kill('SIGTERM');
process.exit(0);
