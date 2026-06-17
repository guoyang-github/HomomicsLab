import { useEffect, useState, useCallback } from 'react'
import { FolderOpen, Download, Upload, Globe, Tag, Search, Loader2 } from 'lucide-react'
import { domainsApi } from '@/services/api'
import type { DomainListing, DomainPreview } from '@/types/api'
import {
  Button,
  Input,
  Badge,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  EmptyState,
  Modal,
} from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import { useTranslation } from '@/i18n'

export function DomainMarketplace() {
  const { t } = useTranslation()
  const [domains, setDomains] = useState<DomainListing[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importSource, setImportSource] = useState('')
  const [importing, setImporting] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [previewDomain, setPreviewDomain] = useState<DomainListing | null>(null)
  const [previewData, setPreviewData] = useState<DomainPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

  const fetchDomains = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await domainsApi.listDomains()
      setDomains(res.data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || t('domain.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDomains()
  }, [fetchDomains])

  const handleExport = async (domainId: string) => {
    try {
      await domainsApi.exportDomain(domainId)
      toastSuccess(`${t('domain.export')} ${domainId}`)
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('domain.exportFailed'))
    }
  }

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!importSource.trim()) return
    setImporting(true)
    setError(null)
    try {
      const res = await domainsApi.importDomain(importSource.trim())
      toastSuccess(`${t('domain.import')} ${res.data.domain_id}`)
      setImportSource('')
      await fetchDomains()
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('domain.importFailed'))
    } finally {
      setImporting(false)
    }
  }

  const handlePreview = async (domain: DomainListing) => {
    setPreviewDomain(domain)
    setPreviewData(null)
    setPreviewError(null)
    setPreviewLoading(true)
    try {
      const res = await domainsApi.previewDomain(domain.domain_id)
      setPreviewData(res.data)
    } catch (err: any) {
      setPreviewError(err?.response?.data?.detail || t('domain.preview.loadFailed'))
    } finally {
      setPreviewLoading(false)
    }
  }

  const closePreview = () => {
    setPreviewDomain(null)
    setPreviewData(null)
    setPreviewError(null)
  }

  const filteredDomains = domains.filter((d) =>
    `${d.name} ${d.description} ${(d.tags || []).join(' ')}`.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background p-4">
      <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">{t('domain.title')}</h2>
          <p className="text-sm text-muted-foreground">{t('domain.subtitle')}</p>
        </div>
        <form onSubmit={handleImport} className="flex items-center gap-2">
          <Input
            value={importSource}
            onChange={(e) => setImportSource(e.target.value)}
            placeholder={t('domain.importPlaceholder')}
            className="w-64"
          />
          <Button type="submit" loading={importing} disabled={!importSource.trim()}>
            <Upload className="mr-1.5 h-4 w-4" />
            {t('domain.import')}
          </Button>
        </form>
      </div>

      <div className="mb-4">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('domain.searchPlaceholder')}
            className="pl-9"
          />
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="h-40 animate-pulse bg-muted" />
            ))}
          </div>
        ) : filteredDomains.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title={t('domain.empty')}
            description={t('domain.emptyDesc')}
            action={{ label: t('common.refresh'), onClick: fetchDomains }}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredDomains.map((domain) => (
              <Card key={domain.domain_id} className="flex flex-col transition-shadow hover:shadow-soft">
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Globe className="h-5 w-5 shrink-0 text-primary" />
                      <CardTitle className="truncate text-base">{domain.name}</CardTitle>
                    </div>
                    <Badge variant="outline" size="sm" className="shrink-0">v{domain.version}</Badge>
                  </div>
                  <CardDescription className="line-clamp-2">{domain.description || t('domain.noDescription')}</CardDescription>
                </CardHeader>
                <CardContent className="flex-1">
                  <div className="flex flex-wrap gap-1.5">
                    {(domain.tags || []).map((tag, idx) => (
                      <Badge key={`${tag}-${idx}`} variant="secondary" size="sm">
                        <Tag className="mr-1 h-3 w-3" />
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <p className="mt-3 text-xs text-muted-foreground">{t('domain.sourceLabel', { source: domain.source })}</p>
                  {domain.author && <p className="text-xs text-muted-foreground">{t('domain.authorLabel', { author: domain.author })}</p>}
                </CardContent>
                <CardFooter className="justify-end gap-2 border-t border-border pt-4">
                  <Button size="sm" variant="outline" onClick={() => handleExport(domain.domain_id)}>
                    <Download className="mr-1.5 h-3.5 w-3.5" />
                    {t('domain.export')}
                  </Button>
                  <Button size="sm" onClick={() => handlePreview(domain)}>
                    {t('domain.preview')}
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={!!previewDomain}
        onClose={closePreview}
        title={previewDomain?.name || t('domain.preview.title')}
        description={previewDomain?.description || ''}
        footer={
          <Button variant="ghost" onClick={closePreview}>{t('domain.close')}</Button>
        }
      >
        {previewLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {previewError && (
          <div className="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {previewError}
          </div>
        )}

        {previewData && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div><span className="text-muted-foreground">{t('domain.preview.version')}</span> <span className="ml-1 font-medium">{previewData.version}</span></div>
              <div><span className="text-muted-foreground">{t('domain.preview.author')}</span> <span className="ml-1 font-medium">{previewData.author || '-'}</span></div>
            </div>

            {previewData.orchestrator_skills.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.orchestratorSkills')} ({previewData.orchestrator_skills.length})</h4>
                <div className="flex max-h-40 flex-wrap gap-1.5 overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                  {previewData.orchestrator_skills.map((skill, idx) => (
                    <Badge key={idx} variant="secondary" size="sm">{skill}</Badge>
                  ))}
                </div>
              </div>
            )}

            {previewData.phases.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.phases')} ({previewData.phases.length})</h4>
                <ul className="max-h-48 overflow-auto rounded-lg border border-border bg-muted/30 p-2 text-xs">
                  {previewData.phases.map((phase) => (
                    <li key={phase.id} className="py-1">
                      <span className="font-medium">{phase.id}</span>
                      <Badge variant="outline" size="sm" className="ml-2">
                        {phase.required ? t('domain.preview.required') : t('domain.preview.optional')}
                      </Badge>
                      {phase.description && <span className="ml-2 text-muted-foreground">{phase.description}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {previewData.phase_transitions.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.phaseTransitions')} ({previewData.phase_transitions.length})</h4>
                <ul className="max-h-40 overflow-auto rounded-lg border border-border bg-muted/30 p-2 text-xs">
                  {previewData.phase_transitions.map((transition, idx) => (
                    <li key={idx} className="py-1">
                      {transition.from} <span className="text-muted-foreground">→</span> {transition.to}
                      {transition.type && <span className="ml-2 text-muted-foreground">({transition.type})</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {previewData.intents.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.intents')} ({previewData.intents.length})</h4>
                <ul className="max-h-40 overflow-auto rounded-lg border border-border bg-muted/30 p-2 text-xs">
                  {previewData.intents.map((intent, idx) => (
                    <li key={idx} className="py-1">
                      <span className="font-medium">{intent.type}</span>
                      {intent.description && <span className="ml-2 text-muted-foreground">{intent.description}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {previewData.skills.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.skills')} ({previewData.skills.length})</h4>
                <div className="flex max-h-40 flex-wrap gap-1.5 overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                  {previewData.skills.map((skill, idx) => (
                    <Badge key={idx} variant="secondary" size="sm">{skill}</Badge>
                  ))}
                </div>
              </div>
            )}

            {previewData.roles.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.roles')} ({previewData.roles.length})</h4>
                <ul className="max-h-40 overflow-auto rounded-lg border border-border bg-muted/30 p-2 text-xs">
                  {previewData.roles.map((role) => (
                    <li key={role.role_id} className="py-1">
                      <span className="font-medium">{role.name || role.role_id}</span>
                      {role.allowed_skills && (
                        <span className="ml-2 text-muted-foreground">{role.allowed_skills.length} skills</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {previewData.sops.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.sops')} ({previewData.sops.length})</h4>
                <div className="max-h-48 space-y-2 overflow-auto rounded-lg border border-border bg-muted/30 p-2 text-xs">
                  {previewData.sops.map((sop) => (
                    <div key={sop.id}>
                      <span className="font-medium">{sop.title || sop.id}</span>
                      {sop.steps && (
                        <ol className="ml-4 mt-1 list-decimal text-muted-foreground">
                          {sop.steps.map((step, idx) => (
                            <li key={idx}>{step}</li>
                          ))}
                        </ol>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(previewData.code_templates).length > 0 && (
              <div>
                <h4 className="mb-2 font-medium text-foreground">{t('domain.preview.templates')} ({Object.keys(previewData.code_templates).length})</h4>
                <ul className="text-xs text-muted-foreground">
                  {Object.entries(previewData.code_templates).map(([name, tmpl]) => (
                    <li key={name}>• {name} {tmpl.language ? `(${tmpl.language})` : ''}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
