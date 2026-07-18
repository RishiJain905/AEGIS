import { defineConfig, devices } from '@playwright/test';

const browserProjects = [
  { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  { name: 'webkit', use: { ...devices['Desktop Safari'] } },
];

const requestedBrowsers = (process.env.AEGIS_BROWSER_PROJECTS ?? 'chromium')
  .split(',')
  .map((name) => name.trim())
  .filter(Boolean);

const chromiumExecutablePath = process.env.AEGIS_CHROMIUM_EXECUTABLE_PATH;
const chromiumProject = {
  name: 'chromium',
  use: {
    ...devices['Desktop Chrome'],
    ...(chromiumExecutablePath
      ? { launchOptions: { executablePath: chromiumExecutablePath } }
      : {}),
  },
};

const webPort = process.env.AEGIS_E2E_WEB_PORT ?? '3000';
const localWeb = process.env.AEGIS_E2E_LOCAL_WEB === '1';

export default defineConfig({
  testDir: '../../tests/e2e',
  fullyParallel: true,
  workers: process.env.AEGIS_E2E_WORKERS ? Number(process.env.AEGIS_E2E_WORKERS) : undefined,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.AEGIS_E2E_BASE_URL ?? `http://127.0.0.1:${webPort}`,
    trace: 'on-first-retry',
  },
  projects: [chromiumProject, ...browserProjects.slice(1)].filter((project) =>
    requestedBrowsers.includes(project.name),
  ),
  webServer: {
    command: localWeb
      ? `pnpm --filter @aegis/web exec next dev --port ${webPort}`
      : 'pnpm --filter @aegis/web start',
    url: `http://127.0.0.1:${webPort}`,
    reuseExistingServer: localWeb ? false : !process.env.CI,
    timeout: 120_000,
  },
});
