/**
 * Capture Phase 31 observability evidence screenshots with Playwright.
 */
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(
  path.resolve(__dirname, '../node_modules/.pnpm/playwright@1.55.1/node_modules/playwright'),
);

const evidence = path.resolve(__dirname, '../docs/handoffs/evidence/phase-31');
const htmlPath = path.join(evidence, 'ops-dashboard.html');

async function shot(page, name, fullPage = true) {
  await page.screenshot({
    path: path.join(evidence, name),
    fullPage,
  });
  console.log('wrote', name);
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.goto(`file://${htmlPath}`);
  await shot(page, '01-ops-dashboard-overview.png');

  for (const [id, file] of [
    ['health', '02-health-liveness.png'],
    ['ready', '03-readiness-dependencies.png'],
    ['authz', '04-protected-endpoint-authz.png'],
    ['failure-recovery', '05-dependency-failure-recovery.png'],
    ['correlation', '06-correlation-headers.png'],
    ['diagnostics', '07-admin-diagnostics.png'],
    ['metrics', '08-admin-metrics.png'],
    ['redaction', '09-redaction-evidence.png'],
    ['grafana-note', '10-dashboard-inventory.png'],
  ]) {
    const el = page.locator(`#${id}`);
    await el.scrollIntoViewIfNeeded();
    await el.screenshot({ path: path.join(evidence, file) });
    console.log('wrote', file);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`file://${htmlPath}`);
  await shot(page, '11-responsive-ops-view.png');

  try {
    await page.setViewportSize({ width: 1440, height: 900 });
    const web = await page.goto('http://127.0.0.1:3000/sign-in', { timeout: 5000 });
    if (web && web.ok()) {
      await shot(page, '12-command-centre-sign-in.png', false);
    }
  } catch {
    console.log('web not available; skipped command-centre screenshot');
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
