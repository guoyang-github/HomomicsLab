#!/usr/bin/env node
/**
 * Generate frontend/public/config.json at container startup.
 *
 * This allows the same frontend Docker image to be reused across environments
 * (dev/staging/prod) without rebuilding. Runtime values are taken from the
 * container environment; fallbacks keep the default single-host behavior.
 */

const fs = require('fs')
const path = require('path')

const publicDir = process.argv[2] || path.join(__dirname, '..', 'dist')
const outputPath = path.join(publicDir, 'config.json')

const config = {
  apiBaseUrl: process.env.HOMOMICS_API_BASE_URL || process.env.VITE_API_BASE_URL || '/api',
  wsUrl: process.env.HOMOMICS_WS_URL || process.env.VITE_WS_URL || '',
}

fs.mkdirSync(publicDir, { recursive: true })
fs.writeFileSync(outputPath, JSON.stringify(config, null, 2) + '\n')

console.log(`Generated ${outputPath}:`, config)
