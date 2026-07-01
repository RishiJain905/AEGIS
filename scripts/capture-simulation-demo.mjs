#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const OUT = '/opt/cursor/artifacts/screenshots';

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

const scenario = 'scenarios/_fixtures/valid-minimal';
const determinism = run(
  `uv run aegis-simulator determinism-check --scenario ${scenario} --seed 42 --steps 30`,
);
const recovery = run(
  `uv run aegis-simulator checkpoint-recovery-check --scenario ${scenario} --seed 42 --steps 30 --checkpoint-at 10`,
);
const divergence = run(
  `uv run aegis-simulator seed-divergence-check --scenario ${scenario} --seed-a 42 --seed-b 99 --steps 30`,
);
const invalid = run('uv run aegis-simulator invalid-command-demo');

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
  <title>AEGIS Phase 09 Simulation Demo</title>
  <style>
    body { margin: 0; background: #111827; color: #e5e7eb; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    main { padding: 32px; display: grid; gap: 24px; }
    h1 { font-size: 20px; margin: 0 0 8px; color: #f9fafb; }
    .panel { background: #1f2937; border: 1px solid #374151; border-radius: 12px; padding: 20px; }
    .panel h2 { margin: 0 0 12px; font-size: 16px; color: #93c5fd; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-word; line-height: 1.5; font-size: 14px; }
    .meta { margin: 12px 0 0; color: #9ca3af; font-size: 12px; }
  </style>
</head>
<body>
  <main>
    <h1>Phase 09 — Deterministic Simulation Core validation evidence</h1>
    ${panel('Determinism check (identical hashes for same seed)', determinism)}
    ${panel('Checkpoint recovery (restored hash matches uninterrupted)', recovery)}
    ${panel('Seed divergence (different seed produces different hash)', divergence)}
    ${panel('Invalid command rejection (agent unauthorized)', invalid)}
  </main>
</body>
</html>`;

const htmlPath = resolve(OUT, '09-simulation-demo.html');
writeFileSync(htmlPath, html, 'utf8');

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto(`file://${htmlPath}`);
await page.waitForTimeout(300);

const panels = page.locator('section.panel');
const titles = [
  '09-determinism-check.png',
  '09-checkpoint-recovery.png',
  '09-seed-divergence.png',
  '09-invalid-command.png',
];
for (let index = 0; index < titles.length; index += 1) {
  await panels.nth(index).screenshot({ path: `${OUT}/${titles[index]}` });
  console.log(`wrote ${OUT}/${titles[index]}`);
}

await browser.close();
