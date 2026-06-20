/** PWA service worker registration helpers. */

export function registerServiceWorker(): void {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
    return
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        // eslint-disable-next-line no-console
        console.log('Service Worker registered:', registration.scope)
      })
      .catch((error) => {
        // eslint-disable-next-line no-console
        console.error('Service Worker registration failed:', error)
      })
  })
}

export function unregisterServiceWorker(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.serviceWorker) {
      resolve()
      return
    }
    navigator.serviceWorker.ready.then((registration) => {
      registration.unregister().then(() => resolve())
    })
  })
}
