import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { registerServiceWorker } from './pwa/serviceWorker'
import { loadRuntimeConfig } from '@/config'
import { setApiBaseUrl } from '@/services/api'

registerServiceWorker()

async function bootstrap() {
  const config = await loadRuntimeConfig()
  setApiBaseUrl(config.apiBaseUrl)

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

bootstrap()
