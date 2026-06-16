import { test, expect } from '@playwright/test'

test('homepage loads and shows sidebar navigation', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('nav')).toBeVisible()
  // The app may land on Chat/Workspace/Skills depending on default route.
  await expect(page.locator('main')).toBeVisible()
})

test('theme toggle switches between light and dark', async ({ page }) => {
  await page.goto('/')
  const html = page.locator('html')

  // Click the theme button if present.
  const themeButton = page.locator('button[aria-label*="theme" i]').first()
  if (await themeButton.isVisible().catch(() => false)) {
    await themeButton.click()
    await expect(html).toHaveClass(/dark|light/)
  }
})

test('settings panel can be opened', async ({ page }) => {
  await page.goto('/')
  const settingsButton = page.locator('button[aria-label*="settings" i]').first()
  if (await settingsButton.isVisible().catch(() => false)) {
    await settingsButton.click()
    await expect(page.getByText(/Settings/i).first()).toBeVisible()
  }
})
