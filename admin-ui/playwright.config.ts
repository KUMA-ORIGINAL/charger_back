import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173/panel/'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    channel: process.env.E2E_CHANNEL || undefined,
    baseURL,
    locale: 'ru-RU',
    timezoneId: 'Asia/Bishkek',
    trace: 'on-first-retry',
  },
  // E2E_CHANNEL=msedge|chrome — системный браузер вместо скачанного Playwright.
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        channel: process.env.E2E_CHANNEL || undefined,
        storageState: 'e2e/.auth/owner.json',
      },
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'corepack pnpm dev',
        url: baseURL,
        reuseExistingServer: !process.env.CI,
      },
})
