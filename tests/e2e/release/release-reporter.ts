import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

import type { FullResult, Reporter, TestCase, TestResult } from '@playwright/test/reporter';

type ReleaseTestResult = {
  id: string;
  title: string;
  project: string;
  status: TestResult['status'];
  durationMs: number;
  error?: string;
};

type ReleaseReport = {
  schemaVersion: 'aegis.release-e2e/v1';
  status: 'passed' | 'failed';
  browsers: string[];
  skippedBrowsers: Array<{ browser: string; reason: string }>;
  tests: ReleaseTestResult[];
};

function skippedBrowsers(): Array<{ browser: string; reason: string }> {
  const raw = process.env.AEGIS_BROWSER_SKIP_REASONS;
  if (!raw) {
    return [];
  }
  try {
    return JSON.parse(raw) as Array<{ browser: string; reason: string }>;
  } catch {
    return [{ browser: 'unknown', reason: 'invalid browser skip metadata' }];
  }
}

export default class ReleaseReporter implements Reporter {
  private readonly tests: ReleaseTestResult[] = [];

  onTestEnd(test: TestCase, result: TestResult): void {
    const project = test.parent.project()?.name ?? 'unknown';
    const error = result.errors[0]?.message;
    this.tests.push({
      id: test.id,
      title: test.titlePath().slice(1).join(' > '),
      project,
      status: result.status,
      durationMs: result.duration,
      ...(error ? { error } : {}),
    });
  }

  onEnd(result: FullResult): void {
    const outputPath = resolve(
      process.env.AEGIS_RELEASE_REPORT_PATH ?? 'docs/release/evidence/e2e.json',
    );
    const report: ReleaseReport = {
      schemaVersion: 'aegis.release-e2e/v1',
      status: result.status === 'passed' ? 'passed' : 'failed',
      browsers: (process.env.AEGIS_BROWSER_PROJECTS ?? 'chromium')
        .split(',')
        .map((browser) => browser.trim())
        .filter(Boolean),
      skippedBrowsers: skippedBrowsers(),
      tests: this.tests,
    };
    mkdirSync(dirname(outputPath), { recursive: true });
    writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  }
}
