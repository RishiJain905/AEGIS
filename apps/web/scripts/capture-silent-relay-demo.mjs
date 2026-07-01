#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../../..');
const OUT = '/opt/cursor/artifacts/screenshots';
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://127.0.0.1:3000';
const SCENARIO = 'scenarios/operation-silent-relay';
const STEPS = 300;

mkdirSync(OUT, { recursive: true });

function run(command) {
  try {
    const stdout = execSync(command, {
      cwd: ROOT,
      encoding: 'utf8',
      env: { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.PATH}` },
    });
    return { exitCode: 0, output: stdout };
  } catch (error) {
    const stdout = error.stdout?.toString?.() ?? '';
    const stderr = error.stderr?.toString?.() ?? '';
    return {
      exitCode: error.status ?? 1,
      output: `${stdout}${stderr}`.trim(),
    };
  }
}

const validate = run(`uv run aegis-scenario validate ${SCENARIO}`);
const determinism = run(
  `uv run aegis-simulator determinism-check --scenario ${SCENARIO} --seed 1000 --steps ${STEPS}`,
);
const divergence = run(
  `uv run aegis-simulator seed-divergence-check --scenario ${SCENARIO} --seed-a 1000 --seed-b 1007 --steps ${STEPS}`,
);
const pytest = run('uv run pytest tests/scenarios/operation_silent_relay tests/golden-replays/operation-silent-relay -q');

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function panel(title, result) {
  return `<section class="panel"><h2>${escapeHtml(title)}</h2><pre><code>${escapeHtml(result.output || '(no output)')}</code></pre><p class="meta">exit=${result.exitCode}</p></section>`;
}

const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Phase 10 Silent Relay Validation</title>
  <style>
    body { margin: 0; background: #111827; color: #e5e7eb; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    main { padding: 32px; display: grid; gap: 24px; }
    h1 { font-size: 20px; margin: 0 0 8px; color: #f9fafb; }
    .panel { background: #1f2937; border: 1px solid #374151; border-radius: 12px; padding: 20px; }
  </style>
</head>
<body>
  <main>
    <header><h1>Operation Silent Relay — Phase 10 validation evidence</h1></header>
    ${panel('aegis-scenario validate', validate)}
    ${panel('determinism-check seed=1000', determinism)}
    ${panel('seed-divergence-check 1000 vs 1007', divergence)}
    ${panel('pytest scenario + golden replays', pytest)}
  </main>
</body>
</html>`;

writeFileSync(`${OUT}/10-validation-evidence.html`, html);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
await page.goto(`file://${OUT}/10-validation-evidence.html`, { waitUntil: 'load' });
await page.screenshot({ path: `${OUT}/10-validation-evidence.png`, fullPage: true });
console.log(`wrote ${OUT}/10-validation-evidence.png`);

const graphPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });

async function shot(name, url, fn = async () => {}) {
  await graphPage.goto(`${BASE}${url}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await fn();
  await graphPage.waitForTimeout(2000);
  const path = `${OUT}/${name}.png`;
  await graphPage.screenshot({ path, fullPage: name.includes('scenarios-list') });
  console.log(`wrote ${path}`);
}

await shot('10-scenarios-list', '/scenarios');

await shot('10-silent-relay-topology-seed-1000', '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0', async () => {
  await graphPage.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 90000 });
});

await shot('10-silent-relay-clusters', '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0', async () => {
  await graphPage.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 90000 });
  const collapse = graphPage.getByTestId('graph-collapse-clusters');
  if (await collapse.isVisible().catch(() => false)) {
    await collapse.click();
  }
});

await shot('10-silent-relay-run-seed-1000', '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0', async () => {
  await graphPage.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 90000 });
  await graphPage.getByTestId('graph-overlay-status').click();
  await graphPage.getByTestId('graph-overlay-risk').click();
});

await shot('10-silent-relay-inspector-evidence', '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB0', async () => {
  await graphPage.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 90000 });
  await graphPage.getByTestId('graph-entity-asset:svc-identity-broker').click();
  await graphPage.waitForSelector('[data-testid=graph-entity-inspector]');
});

await shot('10-silent-relay-run-seed-1007', '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FB1', async () => {
  await graphPage.waitForSelector('[data-testid=operational-graph-canvas]', { timeout: 90000 });
  await graphPage.getByTestId('graph-overlay-status').click();
});

await browser.close();
