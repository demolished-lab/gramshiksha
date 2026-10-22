import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4174',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4174',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    // Enables the opt-in Drive card for its UI test. The production build is
    // given the real public values at build time; tests use harmless stand-ins.
    env: {
      VITE_GOOGLE_CLIENT_ID: 'test-client-id.apps.googleusercontent.com',
      VITE_GOOGLE_PICKER_KEY: 'test-picker-key',
      VITE_GOOGLE_APP_ID: '1234567890',
    },
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], browserName: 'chromium' } },
    { name: 'mobile-chrome', use: { ...devices['iPhone 13'], browserName: 'chromium' } },
    { name: 'mobile-compact', use: { ...devices['iPhone SE'], browserName: 'chromium' } },
  ],
});
