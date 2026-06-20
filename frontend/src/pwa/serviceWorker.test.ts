import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { registerServiceWorker, unregisterServiceWorker } from './serviceWorker'

describe('serviceWorker', () => {
  let swController: Record<string, unknown>

  beforeEach(() => {
    swController = {
      register: vi.fn().mockResolvedValue({ scope: '/' }),
      ready: Promise.resolve({ unregister: vi.fn().mockResolvedValue(undefined) }),
    }
    Object.defineProperty(globalThis.navigator, 'serviceWorker', {
      value: swController,
      configurable: true,
      writable: true,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('registers the service worker after window load', async () => {
    const addEventListener = vi.fn()
    Object.defineProperty(globalThis, 'window', {
      value: { addEventListener },
      configurable: true,
      writable: true,
    })

    registerServiceWorker()
    expect(addEventListener).toHaveBeenCalledWith('load', expect.any(Function))

    const handler = addEventListener.mock.calls[0][1] as () => void
    handler()

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(swController.register).toHaveBeenCalledWith('/sw.js')
  })

  it('unregisters the service worker', async () => {
    await unregisterServiceWorker()
    expect(swController.ready).toBeDefined()
  })

  it('does nothing when service workers are unsupported', () => {
    Object.defineProperty(globalThis.navigator, 'serviceWorker', {
      value: undefined,
      configurable: true,
      writable: true,
    })
    expect(() => registerServiceWorker()).not.toThrow()
  })
})
