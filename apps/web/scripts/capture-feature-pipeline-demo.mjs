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
const STEPS = 120;
const SEED = 1000;

mkdirSync(OUT, { recursive: true });

const env = {
  ...process.env,
  PATH: `${process.env.HOME}/.local/bin:${process.env.PATH}`,
  NEXT_PUBLIC_AEGIS_DATA_SOURCE: 'fixture',
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

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

const simRun = run(
  `uv run aegis-simulator run --scenario ${SCENARIO} --seed ${SEED} --steps ${STEPS}`,
);
const featureEvidence = run('uv run python scripts/render_feature_pipeline_evidence.py');
const parityTests = run(
  'uv run pytest tests/ml/features/test_offline_online_parity.py tests/ml/features/test_determinism.py -q',
);
const rejectionTests = run(
  'uv run pytest tests/ml/features/test_input_guard.py tests/ml/features/test_ordering.py tests/ml/features/test_hidden_truth_leakage.py -q',
);
const mlSuite = run('uv run pytest tests/ml/features -q');

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

await shot('14-silent-relay-command-centre', `${WEB_BASE}/scenarios`);

const evidencePath = resolve(ROOT, '/opt/cursor/artifacts/feature-pipeline-evidence.html');
const evidenceHtml = run(`cat ${evidencePath}`).output;
writeFileSync(resolve(OUT, 'feature-pipeline-evidence.html'), evidenceHtml);

await shot('14-persisted-events-selected', `file://${evidencePath}#events`);
await shot('14-feature-window-row', `file://${evidencePath}#feature-row`);
await shot('14-offline-online-parity', `file://${evidencePath}#parity`);
await shot('14-deterministic-repeat', `file://${evidencePath}#determinism`);
await shot('14-invalid-input-handling', `file://${evidencePath}#rejections`);
await shot('14-dataset-metadata', `file://${evidencePath}#dataset`);

await shot('14-feature-api-observability', `${API_BASE}/features/observability`, async () => {
  await page.waitForTimeout(1000);
});

await browser.close();
web.kill('SIGTERM');
api.kill('SIGTERM');

const summary = {
  simRun: simRun.exitCode === 0,
  featureEvidence: featureEvidence.exitCode === 0,
  parityTests: parityTests.output,
  rejectionTests: rejectionTests.output,
  mlSuite: mlSuite.output,
};
writeFileSync(resolve(OUT, '14-capture-summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
