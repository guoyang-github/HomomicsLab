export interface RuntimeConfig {
  apiBaseUrl: string
  wsUrl: string
}

const DEFAULT_CONFIG: RuntimeConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  wsUrl: import.meta.env.VITE_WS_URL || '',
}

let runtimeConfig: RuntimeConfig | null = null

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  if (runtimeConfig) return runtimeConfig

  try {
    const response = await fetch('/config.json', {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const data = (await response.json()) as Partial<RuntimeConfig>
    runtimeConfig = {
      apiBaseUrl: data.apiBaseUrl || DEFAULT_CONFIG.apiBaseUrl,
      wsUrl: data.wsUrl || DEFAULT_CONFIG.wsUrl,
    }
  } catch {
    runtimeConfig = DEFAULT_CONFIG
  }

  return runtimeConfig
}

export function getRuntimeConfig(): RuntimeConfig {
  if (!runtimeConfig) {
    return DEFAULT_CONFIG
  }
  return runtimeConfig
}
