#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync, spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
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
const idempotency = run('uv run pytest tests/integration/streaming/test_idempotent_consumer.py -q');
const dlq = run('uv run pytest tests/integration/streaming/test_dead_letter.py -q');
const recovery = run('uv run pytest tests/integration/streaming/test_relay_crash_recovery.py -q');
const backfillTest = run('uv run pytest tests/integration/streaming/test_redis_rebuild.py -q');
const streamingSuite = run('uv run pytest tests/integration/streaming -q');

const api = spawn('uv', ['run', 'aegis-api'], { cwd: ROOT, env, stdio: 'ignore' });
await new Promise((resolve) => setTimeout(resolve, 4000));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

async function shot(name, url, fn = async () => {}) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await fn();
  await page.waitForTimeout(1500);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  console.log(`wrote ${path}`);
}

await shot('11-streaming-observability', `${API_BASE}/realtime/observability`);
await page.fill('#runId', runId);
await page.click('button');
await page.waitForTimeout(2000);
await page.screenshot({ path: `${OUT}/11-pg-event-history.png`, fullPage: true });
console.log(`wrote ${OUT}/11-pg-event-history.png`);

await shot('11-redis-stream-status', `${API_BASE}/api/v1/realtime/streaming/status`);

const evidenceHtml = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><title>Phase 11 Streaming Evidence</title>
<style>body{margin:0;background:#111827;color:#e5e7eb;font-family:ui-monospace,Menlo,monospace}main{padding:32px;display:grid;gap:24px}h1{font-size:20px}.panel{background:#1f2937;border:1px solid #374151;border-radius:12px;padding:20px}</style>
</head><body><main><h1>Phase 11 event streaming validation</h1>
<p>Run ID: ${escapeHtml(runId)}</p>
${panel('run-persisted Silent Relay', persisted)}
${panel('outbox relay publish', relay)}
${panel('idempotency integration test', idempotency)}
${panel('dead letter integration test', dlq)}
${panel('relay crash recovery test', recovery)}
${panel('redis rebuild backfill test', backfillTest)}
${panel('full streaming suite', streamingSuite)}
</main></body></html>`;
writeFileSync(`${OUT}/11-streaming-validation-evidence.html`, evidenceHtml);
await page.goto(`file://${OUT}/11-streaming-validation-evidence.html`);
await page.screenshot({ path: `${OUT}/11-idempotency-dlq-recovery-evidence.png`, fullPage: true });
console.log(`wrote ${OUT}/11-idempotency-dlq-recovery-evidence.png`);

const webPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await webPage.goto(`${WEB_BASE}/scenarios`, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
await webPage.waitForTimeout(2000);
await webPage.screenshot({ path: `${OUT}/11-command-centre-frontend.png`, fullPage: true });
console.log(`wrote ${OUT}/11-command-centre-frontend.png`);

await browser.close();
api.kill('SIGTERM');
process.exit(0);
