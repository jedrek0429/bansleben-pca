import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.PCA_TEST_PORT || 4173);
const siteDist = process.env.PCA_SITE_DIST || '../site-dist';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]]
    : [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  webServer: {
    command: `python -m http.server ${port} --directory ${siteDist}`,
    url: `http://127.0.0.1:${port}/en/`,
    reuseExistingServer: !process.env.CI,
    timeout: 15_000,
  },
  expect: {
    timeout: 5_000,
    toHaveScreenshot: process.env.PCA_STRICT_PIXELS === '1'
      ? { maxDiffPixels: 0 }
      : { maxDiffPixelRatio: 0.002 },
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: 'chromium-tablet',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: 'chromium-mobile',
      use: {
        ...devices['Pixel 5'],
      },
    },
  ],
});
