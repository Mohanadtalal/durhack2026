import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  testMatch: '**/audit.spec.js',
  timeout: 45000,
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium',
         headless: true, viewport: { width: 1380, height: 880 } },
  retries: 0,
  reporter: 'list',
  workers: 1,
})
