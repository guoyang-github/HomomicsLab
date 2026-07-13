import { test, expect } from '@playwright/test'

const PROMPT = '使用 CellTypist 对 PA12_sc.h5ad 中的免疫细胞进行自动注释，并比较注释结果与现有 all_celltype 标签的一致性'

test('CellTypist chat task shows live progress and result', async ({ page }) => {
  test.setTimeout(600_000)

  const logs: string[] = []
  page.on('console', (msg) => {
    const text = msg.text()
    if (text.includes('[useExecutionSSE]') || text.includes('[TodoList]')) {
      logs.push(text)
    }
  })

  await page.goto('/')

  // Clear persisted sessions/state so the chat send path does not load a huge
  // history, which can make the initial response take minutes.
  await page.evaluate(async () => {
    localStorage.clear()
    sessionStorage.clear()
    const dbs = await window.indexedDB.databases?.().catch(() => [])
    for (const db of dbs) {
      if (db.name) window.indexedDB.deleteDatabase(db.name)
    }
  })
  await page.reload()

  // Wait for the chat input to be ready.
  const textarea = page.locator('textarea').first()
  await expect(textarea).toBeVisible({ timeout: 10_000 })

  // Fill and send.
  await textarea.fill(PROMPT)
  await page.keyboard.press('Enter')

  // The backend planning/intent analysis can take 30-60s on first run.
  // Wait for the agent TODO list message to appear.
  try {
    await expect(page.getByText('Automated cell type annotation using CellTypist')).toBeVisible({ timeout: 300_000 })
  } catch (e) {
    // eslint-disable-next-line no-console
    console.log('--- captured logs ---')
    logs.forEach((l) => console.log(l))
    // eslint-disable-next-line no-console
    console.log('--- visible text ---')
    // eslint-disable-next-line no-console
    console.log(await page.locator('body').textContent())
    await page.screenshot({ path: '/tmp/homomics_chat_failure.png', fullPage: true })
    throw e
  }

  // Wait for the running/completed indicator inside the TODO card.
  await expect(page.getByText(/执行中|等待\/已完成|执行完成|执行失败/).first()).toBeVisible({ timeout: 120_000 })

  // Live progress: the TODO card should show at least one stdout log line
  // streamed from the skill (e.g. "Loading ..." or "Running CellTypist").
  try {
    await expect(page.locator('li').filter({ hasText: /Loading|Running CellTypist|AnnData:|Auto-discovered/ }).first()).toBeVisible({ timeout: 120_000 })
  } catch (e) {
    // eslint-disable-next-line no-console
    console.log('--- captured logs at live-progress failure ---')
    logs.forEach((l) => console.log(l))
    throw e
  }

  // Wait for completion or failure card.
  const successCard = page.getByText('执行完成')
  const failureCard = page.getByText('执行失败')
  try {
    await expect(successCard.or(failureCard)).toBeVisible({ timeout: 300_000 })
  } catch (e) {
    // eslint-disable-next-line no-console
    console.log('--- captured logs ---')
    logs.forEach((l) => console.log(l))
    await page.screenshot({ path: '/tmp/homomics_chat_failure.png', fullPage: true })
    throw e
  }

  // If success, assert key numbers are shown.
  if (await successCard.isVisible().catch(() => false)) {
    await expect(page.getByText(/细胞数：/)).toBeVisible()
    await expect(page.getByText(/Adjusted Rand Index/)).toBeVisible()
  } else {
    const errorText = await page.getByText('执行失败').locator('..').locator('p').textContent()
    throw new Error(`Execution failed: ${errorText}`)
  }
})
