import { test, expect } from '@playwright/test'

test('phase1: clickable homepage, configured preview, real zone and incident', async ({ page }) => {
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  await page.goto('/')
  const cta = page.getByRole('button', { name: 'Open the dashboard' })
  await expect(cta).toBeVisible()
  // Real pointer action, not a forced/programmatic click.
  await cta.click({ timeout: 10000 })
  await expect(page.locator('h1')).toHaveText('Overview')
  await expect(page.getByText('Camera publishing recent frames').first()).toBeVisible({ timeout: 10000 })
  await expect(page.getByText('Restricted zone 1').first()).toBeVisible()
  await expect(page.locator('.camera-zone-map polygon')).toHaveCount(1)

  const create = await page.request.post('http://127.0.0.1:8000/api/events', {
    data: {
      source_id: 'nicla-vision-01', zone_id: 'nicla-zone-1',
      hazard_type: 'zone_entry', severity: 'warning',
      description: 'Synthetic Phase 1 browser integration event',
      metadata: { simulated: true },
    },
  })
  expect(create.status()).toBe(200)
  await expect(page.locator('.zone-list-row').first()).toContainText('1 recent', { timeout: 10000 })
  await page.locator('.zone-list-row').first().click()
  await expect(page.locator('.zone-list-row').first()).toHaveClass(/zone-list-selected/)

  await page.getByRole('button', { name: 'Camera', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('Camera')
  await expect(page.getByText('Frames arriving').first()).toBeVisible()
  await expect(page.locator('.camera-frame img')).toBeVisible()
  await expect.poll(async () => page.locator('.camera-frame img').evaluate(
    img => img.complete && img.naturalWidth > 0
  )).toBe(true)

  await page.getByRole('button', { name: 'Camera zones', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('Camera zones')
  await expect(page.locator('.camera-zone-map polygon')).toHaveCount(1)
  await expect(page.getByText('Working At Height C')).toHaveCount(0)
  expect(errors).toEqual([])
})
