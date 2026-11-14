import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: '**/phase1.spec.js',
  timeout: 45000,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium',
         headless: true, viewport: { width: 1380, height: 880 } },
})
