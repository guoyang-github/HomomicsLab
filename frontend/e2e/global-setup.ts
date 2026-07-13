import { readdir, rm } from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'
import { FullConfig } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/**
 * E2E global setup.
 *
 * Backend skill/workflow caches must be cleared before each run so that
 * streaming-progress tests actually execute the skill rather than returning
 * a cached result. This only touches local test data directories.
 */
export default async function globalSetup(_config: FullConfig) {
  const dirs = [
    path.resolve(__dirname, '../../data/skill_cache'),
    path.resolve(__dirname, '../../data/workflow_cache'),
    path.resolve(__dirname, '../../backend/data/skill_cache'),
    path.resolve(__dirname, '../../backend/data/workflow_cache'),
  ]

  let removed = 0
  for (const dir of dirs) {
    let entries: string[] = []
    try {
      entries = await readdir(dir, { recursive: true, withFileTypes: false })
    } catch {
      // Directory may not exist; ignore.
      continue
    }
    const pklFiles = entries.filter((name) => name.endsWith('.pkl'))
    await Promise.all(pklFiles.map((name) => rm(path.join(dir, name), { force: true })))
    removed += pklFiles.length
  }
  // eslint-disable-next-line no-console
  console.log(`[global-setup] cleared ${removed} cache files from skill/workflow cache directories`)
}
