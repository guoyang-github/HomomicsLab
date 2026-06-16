import { useEffect, useState, useCallback } from 'react'
import { FolderOpen, Download, Upload, Globe, Tag, Search } from 'lucide-react'
import { domainsApi } from '@/services/api'
import type { DomainListing } from '@/types/api'
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
} from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'

export function DomainMarketplace() {
  const [domains, setDomains] = useState<DomainListing[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importSource, setImportSource] = useState('')
  const [importing, setImporting] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const fetchDomains = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await domainsApi.listDomains()
      setDomains(res.data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载 Domains 失败')
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
      toastSuccess(`已导出 ${domainId}`)
    } catch (err: any) {
      toastError(err?.response?.data?.detail || '导出失败')
    }
  }

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!importSource.trim()) return
    setImporting(true)
    setError(null)
    try {
      const res = await domainsApi.importDomain(importSource.trim())
      toastSuccess(`已导入 ${res.data.domain_id}`)
      setImportSource('')
      await fetchDomains()
    } catch (err: any) {
      toastError(err?.response?.data?.detail || '导入失败')
    } finally {
      setImporting(false)
    }
  }

  const filteredDomains = domains.filter((d) =>
    `${d.name} ${d.description} ${(d.tags || []).join(' ')}`.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background p-4">
      <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Domain 市场</h2>
          <p className="text-sm text-muted-foreground">浏览、导入和导出领域模板</p>
        </div>
        <form onSubmit={handleImport} className="flex gap-2">
          <Input
            value={importSource}
            onChange={(e) => setImportSource(e.target.value)}
            placeholder="domain.yaml 路径或 URL"
            className="w-64"
          />
          <Button type="submit" loading={importing} disabled={!importSource.trim()}>
            <Upload className="mr-1.5 h-4 w-4" />
            导入
          </Button>
        </form>
      </div>

      <div className="mb-4">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索 domain..."
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
            title="暂无 Domains"
            description="导入或创建领域模板以开始使用"
            action={{ label: '刷新', onClick: fetchDomains }}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredDomains.map((domain) => (
              <Card key={domain.id} className="flex flex-col transition-shadow hover:shadow-soft">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <Globe className="h-5 w-5 text-primary" />
                      <CardTitle className="text-base">{domain.name}</CardTitle>
                    </div>
                    <Badge variant="outline" size="sm">v{domain.version}</Badge>
                  </div>
                  <CardDescription>{domain.description || '无描述'}</CardDescription>
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
                  <p className="mt-3 text-xs text-muted-foreground">来源：{domain.source}</p>
                  <p className="text-xs text-muted-foreground">作者：{domain.author}</p>
                </CardContent>
                <CardFooter className="justify-end gap-2 border-t border-border pt-4">
                  <Button size="sm" variant="outline" onClick={() => handleExport(domain.id)}>
                    <Download className="mr-1.5 h-3.5 w-3.5" />
                    导出
                  </Button>
                  <Button size="sm" onClick={() => {}}>
                    预览
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
