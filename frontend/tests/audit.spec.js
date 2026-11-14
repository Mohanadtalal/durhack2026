import { test, expect } from '@playwright/test'

// Browser visits the actual Vite app; FastAPI is served separately on :8000.
// The Gemini account is deliberately unconfigured; 503 is the correct result.
test('dashboard end-to-end: navigation, practice incident, filters, details, Gemini error', async ({ page }) => {
  const errors = []
  page.on('pageerror', err => errors.push(err.message))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Open the dashboard' })).toBeVisible()
  // Known product issue: the landing page's sticky scroll animation can
  // cover the primary CTA. Use the top navigation to audit the app itself.
  await page.getByRole('button', { name: 'Overview', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('Overview')
  await expect(page.getByText('Connected', { exact: true }).first()).toBeVisible()

  await page.locator('details.sim summary').click()
  await page.getByRole('button', { name: 'Practice: someone enters a zone' }).click()
  await expect(page.getByText('Simulated', { exact: true }).first()).toBeVisible({ timeout: 10000 })
  await page.screenshot({ path: 'audit-overview.png', fullPage: true })

  await page.getByRole('button', { name: 'History', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('History')
  await expect(page.locator('.incidents .incident').first()).toBeVisible()
  await page.locator('.incidents .incident').first().click()
  await expect(page.getByRole('dialog', { name: 'Incident detail' })).toBeVisible()
  await expect(page.getByText('Event ID', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Close detail' }).click()
  await page.screenshot({ path: 'audit-history.png', fullPage: true })

  await page.getByRole('button', { name: 'AI review', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('AI review')
  await page.getByRole('button', { name: /Ask Gemini to review the incidents/ }).click()
  await expect(page.getByText(/GEMINI_API_KEY is not configured/)).toBeVisible({ timeout: 10000 })
  await page.screenshot({ path: 'audit-gemini.png', fullPage: true })

  await page.getByRole('button', { name: 'Camera', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('Camera')
  await expect(page.getByText('No camera connected', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'audit-camera.png', fullPage: true })

  await page.getByRole('button', { name: 'Site map', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('Site map')
  await expect(page.getByText('Schematic plan, not to scale')).toBeVisible()
  await page.screenshot({ path: 'audit-map.png', fullPage: true })

  expect(errors).toEqual([])
})

