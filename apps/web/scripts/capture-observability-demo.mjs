import { chromium } from '@playwright/test';
import path from 'node:path';

const evidence = path.resolve('../../docs/handoffs/evidence/phase-31');
const htmlPath = path.join(evidence, 'ops-dashboard.html');

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`file://${htmlPath}`);
  await page.screenshot({
    path: path.join(evidence, '01-ops-dashboard-overview.png'),
    fullPage: true,
  });
  const pairs = [
    ['health', '02-health-liveness.png'],
    ['ready', '03-readiness-dependencies.png'],
    ['authz', '04-protected-endpoint-authz.png'],
    ['failure-recovery', '05-dependency-failure-recovery.png'],
    ['correlation', '06-correlation-headers.png'],
    ['diagnostics', '07-admin-diagnostics.png'],
    ['metrics', '08-admin-metrics.png'],
    ['redaction', '09-redaction-evidence.png'],
    ['grafana-note', '10-dashboard-inventory.png'],
  ];
  for (const [id, file] of pairs) {
    const el = page.locator(`#${id}`);
    await el.scrollIntoViewIfNeeded();
    await el.screenshot({ path: path.join(evidence, file) });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`file://${htmlPath}`);
  await page.screenshot({
    path: path.join(evidence, '11-responsive-ops-view.png'),
    fullPage: true,
  });
  await browser.close();
  console.log('screenshots complete');
}

main();
