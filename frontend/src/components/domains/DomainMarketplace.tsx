import { useEffect, useState } from 'react'
import { domainsApi } from '@/services/api'
import type { DomainListing } from '@/types/api'

export function DomainMarketplace() {
  const [domains, setDomains] = useState<DomainListing[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importSource, setImportSource] = useState('')
  const [importing, setImporting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const fetchDomains = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await domainsApi.listDomains()
      setDomains(res.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load domains')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDomains()
  }, [])

  const handleExport = async (domainId: string) => {
    setMessage(null)
    try {
      const res = await domainsApi.exportDomain(domainId)
      setMessage(`Exported ${domainId} to ${res.data.exported_to}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
    }
  }

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!importSource.trim()) return
    setImporting(true)
    setMessage(null)
    setError(null)
    try {
      const res = await domainsApi.importDomain(importSource.trim())
      setMessage(`Imported ${res.data.domain_id} to ${res.data.domain_dir}`)
      setImportSource('')
      await fetchDomains()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-white p-4">
      <h3 className="mb-4 text-base font-semibold text-slate-800">Domain Marketplace</h3>

      <form onSubmit={handleImport} className="mb-4 flex gap-2">
        <input
          type="text"
          value={importSource}
          onChange={(e) => setImportSource(e.target.value)}
          placeholder="Path or URL to domain.yaml / domain directory"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        />
        <button
          type="submit"
          disabled={importing || !importSource.trim()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
        >
          {importing ? 'Importing…' : 'Import'}
        </button>
      </form>

      {error && <div className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
      {message && <div className="mb-3 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</div>}

      <div className="flex-1 overflow-auto">
        {loading ? (
          <p className="text-sm text-slate-500">Loading domains…</p>
        ) : domains.length === 0 ? (
          <p className="text-sm text-slate-500">No domains available.</p>
        ) : (
          <ul className="space-y-3">
            {domains.map((domain) => (
              <li key={domain.id} className="rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-800">{domain.name}</h4>
                    <p className="mt-1 text-xs text-slate-600">{domain.description}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {domain.tags.map((tag) => (
                        <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => handleExport(domain.id)}
                    className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                  >
                    Export
                  </button>
                </div>
                <div className="mt-2 text-xs text-slate-400">
                  v{domain.version} · {domain.author} · {domain.source}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
