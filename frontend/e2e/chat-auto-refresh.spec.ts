import { test, expect } from '@playwright/test'

const PROMPT = '@file:PA12_small.h5ad 使用 CellTypist 对 PA12_small.h5ad 中的免疫细胞进行自动注释，并比较注释结果与现有 all_celltype 标签的一致性，结果写入 outputs/ 并在对话中总结。'

test('CellTypist result appears automatically without manual refresh', async ({ page }) => {
  test.setTimeout(600_000)

  const logs: string[] = []
  page.on('console', (msg) => {
    const text = msg.text()
    if (text.includes('[useExecutionSSE]') || text.includes('[chatStore]')) {
      logs.push(text)
    }
  })

  await page.goto('/')

  // Clear persisted sessions/state.
  await page.evaluate(async () => {
    localStorage.clear()
    sessionStorage.clear()
    const dbs = await window.indexedDB.databases?.().catch(() => [])
    for (const db of dbs) {
      if (db.name) window.indexedDB.deleteDatabase(db.name)
    }
  })
  await page.reload()

  const textarea = page.locator('textarea').first()
  await expect(textarea).toBeVisible({ timeout: 10_000 })

  await textarea.fill(PROMPT)
  await page.keyboard.press('Enter')

  // Wait for the TODO card to appear.
  try {
    await expect(page.getByText('Automated cell type annotation using CellTypist')).toBeVisible({ timeout: 300_000 })
  } catch (e) {
    // eslint-disable-next-line no-console
    console.log('--- captured logs ---')
    logs.forEach((l) => console.log(l))
    await page.screenshot({ path: '/tmp/homomics_chat_auto_refresh_failure_todo.png', fullPage: true })
    throw e
  }

  // Wait for completion.
  const successCard = page.getByText('执行完成')
  const failureCard = page.getByText('执行失败')
  try {
    await expect(successCard.or(failureCard)).toBeVisible({ timeout: 300_000 })
  } catch (e) {
    // eslint-disable-next-line no-console
    console.log('--- captured logs ---')
    logs.forEach((l) => console.log(l))
    await page.screenshot({ path: '/tmp/homomics_chat_auto_refresh_failure_complete.png', fullPage: true })
    throw e
  }

  if (await failureCard.isVisible().catch(() => false)) {
    // eslint-disable-next-line no-console
    console.log('--- captured logs ---')
    logs.forEach((l) => console.log(l))
    throw new Error('Execution failed')
  }

  // After completion, the detailed summary message should appear automatically
  // without any manual refresh. We wait for a distinctive piece of the summary.
  try {
    await expect(page.getByText(/关键指标|细胞数：|CellTypist 注释结果/).first()).toBeVisible({ timeout: 30_000 })
  } catch (e) {
    // eslint-disable-next-line no-console
    console.log('--- captured logs at auto-refresh failure ---')
    logs.forEach((l) => console.log(l))
    await page.screenshot({ path: '/tmp/homomics_chat_auto_refresh_failure_summary.png', fullPage: true })
    throw e
  }
})
