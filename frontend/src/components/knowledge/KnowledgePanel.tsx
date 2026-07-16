import { useEffect, useRef, useState } from 'react'
import {
  BookOpen,
  Bot,
  Eye,
  FileText,
  Loader2,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useProjectStore } from '@/stores/projectStore'
import {
  knowledgeApi,
  type KnowledgeDocument,
  type KnowledgeDocumentDetail,
  type WikiPage,
  type WikiAskResult,
} from '@/services/knowledgeApi'
import { Button } from '@/components/ui'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/shadcn/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'

export function KnowledgePanel() {
  const { t } = useTranslation()
  const projectId = useProjectStore((state) => state.currentProjectId)
  const [activeTab, setActiveTab] = useState('documents')

  // Documents state
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [docLoading, setDocLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [docQuery, setDocQuery] = useState('')
  const [searchResults, setSearchResults] = useState<{ id: string; text: string; score?: number }[] | null>(null)
  const [searching, setSearching] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null)
  const [detail, setDetail] = useState<KnowledgeDocumentDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [editedTitle, setEditedTitle] = useState('')
  const [editedSummary, setEditedSummary] = useState('')
  const [saving, setSaving] = useState(false)
  const [generatingWiki, setGeneratingWiki] = useState<string | null>(null)

  // Wiki state
  const [wikiPages, setWikiPages] = useState<WikiPage[]>([])
  const [wikiLoading, setWikiLoading] = useState(false)
  const [wikiSearchQuery, setWikiSearchQuery] = useState('')
  const [selectedWikiPage, setSelectedWikiPage] = useState<WikiPage | null>(null)
  const [wikiEditTitle, setWikiEditTitle] = useState('')
  const [wikiEditContent, setWikiEditContent] = useState('')
  const [wikiSaving, setWikiSaving] = useState(false)
  const [showCreateWiki, setShowCreateWiki] = useState(false)
  const [newWikiTitle, setNewWikiTitle] = useState('')
  const [newWikiContent, setNewWikiContent] = useState('')

  // Ask state
  const [askQuestion, setAskQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askResult, setAskResult] = useState<WikiAskResult | null>(null)

  const fetchDocuments = async () => {
    setDocLoading(true)
    setError(null)
    try {
      const res = await knowledgeApi.listDocuments(projectId)
      setDocuments(res.data.documents || [])
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || t('knowledge.loadError'))
    } finally {
      setDocLoading(false)
    }
  }

  const fetchWikiPages = async (q?: string) => {
    setWikiLoading(true)
    setError(null)
    try {
      const res = await knowledgeApi.listWikiPages(projectId, q)
      setWikiPages(res.data || [])
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '加载 Wiki 失败')
    } finally {
      setWikiLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments()
    fetchWikiPages()
  }, [projectId])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await knowledgeApi.ingestUpload(file, projectId)
      await fetchDocuments()
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || t('knowledge.uploadError'))
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDocSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!docQuery.trim()) {
      setSearchResults(null)
      return
    }
    setSearching(true)
    setError(null)
    try {
      const res = await knowledgeApi.search(docQuery.trim(), projectId)
      setSearchResults(
        (res.data.results || []).map((r) => ({
          id: r.id,
          text: r.text,
          score: typeof r.score === 'number' ? r.score : undefined,
        }))
      )
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || t('knowledge.searchError'))
      setSearchResults(null)
    } finally {
      setSearching(false)
    }
  }

  const openDetail = async (doc: KnowledgeDocument) => {
    setSelectedDoc(doc)
    setDetail(null)
    setDetailLoading(true)
    setDetailError(null)
    setEditedTitle(doc.title || '')
    setEditedSummary(doc.summary || '')
    try {
      const res = await knowledgeApi.getDocument(doc.document_id)
      const data = res.data || {}
      setDetail({
        document_id: data.document_id || doc.document_id,
        chunks: data.chunks || [],
        entities: data.entities || [],
        edges: data.edges || [],
      })
    } catch (err: any) {
      setDetailError(err?.response?.data?.detail || err?.message || '加载文档详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDetail = () => {
    setSelectedDoc(null)
    setDetail(null)
    setDetailError(null)
  }

  const saveDetail = async () => {
    if (!selectedDoc) return
    setSaving(true)
    setDetailError(null)
    try {
      await knowledgeApi.updateDocument(selectedDoc.document_id, projectId, {
        title: editedTitle,
        summary: editedSummary,
      })
      setDocuments((prev) =>
        prev.map((d) =>
          d.document_id === selectedDoc.document_id
            ? { ...d, title: editedTitle, summary: editedSummary }
            : d
        )
      )
      setSelectedDoc((prev) => (prev ? { ...prev, title: editedTitle, summary: editedSummary } : prev))
    } catch (err: any) {
      setDetailError(err?.response?.data?.detail || err?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleGenerateWiki = async (doc: KnowledgeDocument) => {
    setGeneratingWiki(doc.document_id)
    setError(null)
    try {
      await knowledgeApi.generateWikiPages(doc.document_id, projectId)
      setActiveTab('wiki')
      await fetchWikiPages()
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '生成 Wiki 失败')
    } finally {
      setGeneratingWiki(null)
    }
  }

  const openWikiPage = async (page: WikiPage) => {
    setWikiSaving(false)
    setSelectedWikiPage(page)
    setWikiEditTitle(page.title)
    setWikiEditContent(page.content)
  }

  const closeWikiPage = () => {
    setSelectedWikiPage(null)
    setWikiEditTitle('')
    setWikiEditContent('')
  }

  const saveWikiPage = async () => {
    if (!selectedWikiPage) return
    setWikiSaving(true)
    setError(null)
    try {
      await knowledgeApi.updateWikiPage(selectedWikiPage.page_id, projectId, {
        title: wikiEditTitle,
        content: wikiEditContent,
      })
      await fetchWikiPages(wikiSearchQuery)
      setSelectedWikiPage((prev) =>
        prev ? { ...prev, title: wikiEditTitle, content: wikiEditContent } : prev
      )
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '保存 Wiki 失败')
    } finally {
      setWikiSaving(false)
    }
  }

  const deleteWikiPage = async (page: WikiPage) => {
    if (!confirm(`确定删除 Wiki 页面「${page.title}」吗？`)) return
    setError(null)
    try {
      await knowledgeApi.deleteWikiPage(page.page_id, projectId)
      await fetchWikiPages(wikiSearchQuery)
      if (selectedWikiPage?.page_id === page.page_id) closeWikiPage()
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '删除 Wiki 失败')
    }
  }

  const createWikiPage = async () => {
    if (!newWikiTitle.trim() || !newWikiContent.trim()) return
    setWikiSaving(true)
    setError(null)
    try {
      await knowledgeApi.createWikiPage(projectId, {
        title: newWikiTitle.trim(),
        content: newWikiContent.trim(),
      })
      setShowCreateWiki(false)
      setNewWikiTitle('')
      setNewWikiContent('')
      await fetchWikiPages(wikiSearchQuery)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '创建 Wiki 失败')
    } finally {
      setWikiSaving(false)
    }
  }

  const handleWikiSearch = (e: React.FormEvent) => {
    e.preventDefault()
    fetchWikiPages(wikiSearchQuery.trim() || undefined)
  }

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!askQuestion.trim()) return
    setAsking(true)
    setError(null)
    try {
      const res = await knowledgeApi.askWiki(askQuestion.trim(), projectId)
      setAskResult(res.data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '问答失败')
      setAskResult(null)
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="flex h-full flex-col bg-background p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-accent" />
          <h1 className="text-lg font-semibold text-foreground">{t('knowledge.title')}</h1>
        </div>
        <div className="text-xs text-muted-foreground">
          {t('common.project')}: {projectId}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <Tabs defaultValue="documents" value={activeTab} onValueChange={setActiveTab} className="min-h-0 flex-1">
        <TabsList className="mb-4 grid w-full grid-cols-3">
          <TabsTrigger value="documents" className="text-xs">
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            文档
          </TabsTrigger>
          <TabsTrigger value="wiki" className="text-xs">
            <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            Wiki
          </TabsTrigger>
          <TabsTrigger value="ask" className="text-xs">
            <Bot className="mr-1.5 h-3.5 w-3.5" />
            问答
          </TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="min-h-0 flex-1">
          <div className="flex h-full flex-col gap-4">
            <div className="rounded-xl border border-border bg-card p-4 shadow-card">
              <div className="mb-3 text-sm font-medium text-foreground">{t('knowledge.upload')}</div>
              <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.md,.markdown,.txt,.html,.htm,.csv,.json,.yaml,.yml,.png,.jpg,.jpeg,.gif,.webp"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="gap-2"
                >
                  {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  {uploading ? t('knowledge.ingesting') : t('knowledge.selectFile')}
                </Button>
                <span className="text-xs text-muted-foreground">{t('knowledge.supportedFormats')}</span>
              </div>
            </div>

            <form onSubmit={handleDocSearch} className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={docQuery}
                  onChange={(e) => setDocQuery(e.target.value)}
                  placeholder={t('knowledge.searchPlaceholder')}
                  className="h-9 w-full rounded-md border border-border bg-surface pl-9 pr-3 text-sm text-foreground outline-none focus:border-accent"
                />
              </div>
              <Button type="submit" disabled={searching || !docQuery.trim()}>
                {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : t('knowledge.search')}
              </Button>
              {searchResults !== null && (
                <Button type="button" variant="ghost" onClick={() => setSearchResults(null)}>
                  <X className="h-4 w-4" />
                </Button>
              )}
            </form>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {searchResults !== null ? (
                <div className="space-y-2">
                  <div className="mb-2 text-sm font-medium text-foreground">
                    {t('knowledge.searchResults')} ({searchResults.length})
                  </div>
                  {searchResults.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{t('knowledge.noSearchResults')}</p>
                  ) : (
                    searchResults.map((r) => (
                      <div
                        key={r.id}
                        className="rounded-lg border border-border bg-surface p-3 text-xs text-foreground"
                      >
                        <div className="mb-1 flex items-center justify-between text-[10px] text-muted-foreground">
                          <span>ID: {r.id}</span>
                          {r.score !== undefined && <span>score: {r.score.toFixed(3)}</span>}
                        </div>
                        <p className="whitespace-pre-wrap leading-relaxed">{r.text}</p>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">
                      {t('knowledge.documents')} ({documents.length})
                    </span>
                    <Button type="button" variant="ghost" size="sm" onClick={fetchDocuments} disabled={docLoading}>
                      {docLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : t('common.refresh')}
                    </Button>
                  </div>
                  {documents.length === 0 && !docLoading ? (
                    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card py-12 text-center">
                      <FileText className="mb-2 h-8 w-8 text-muted-foreground" />
                      <p className="text-sm text-muted-foreground">{t('knowledge.empty')}</p>
                    </div>
                  ) : (
                    documents.map((doc) => (
                      <div
                        key={doc.document_id}
                        className="flex items-start justify-between rounded-lg border border-border bg-card p-3 transition-colors hover:border-accent/30"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 shrink-0 text-accent" />
                            <span className="truncate text-sm font-medium text-foreground">
                              {doc.title || doc.document_id}
                            </span>
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                            {doc.filename && doc.filename !== doc.title && <span>{doc.filename}</span>}
                            <span>{t('knowledge.chunks', { count: doc.chunk_count })}</span>
                            {doc.source_type && <span className="rounded bg-surface px-1.5 py-0.5">{doc.source_type}</span>}
                          </div>
                          {doc.summary && (
                            <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">{doc.summary}</p>
                          )}
                        </div>
                        <div className="ml-2 flex flex-col gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="gap-1"
                            onClick={() => openDetail(doc)}
                          >
                            <Eye className="h-4 w-4" />
                            查看
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="gap-1 text-xs"
                            onClick={() => handleGenerateWiki(doc)}
                            disabled={generatingWiki === doc.document_id}
                          >
                            {generatingWiki === doc.document_id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Sparkles className="h-3.5 w-3.5" />
                            )}
                            生成 Wiki
                          </Button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="wiki" className="min-h-0 flex-1">
          <div className="flex h-full flex-col gap-4">
            <div className="flex items-center gap-2">
              <form onSubmit={handleWikiSearch} className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={wikiSearchQuery}
                  onChange={(e) => setWikiSearchQuery(e.target.value)}
                  placeholder="搜索 Wiki 页面…"
                  className="h-9 w-full rounded-md border border-border bg-surface pl-9 pr-3 text-sm text-foreground outline-none focus:border-accent"
                />
              </form>
              <Button type="button" variant="outline" size="sm" onClick={() => fetchWikiPages(wikiSearchQuery.trim() || undefined)} disabled={wikiLoading}>
                {wikiLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              </Button>
              <Button type="button" size="sm" className="gap-1" onClick={() => setShowCreateWiki(true)}>
                <Plus className="h-4 w-4" />
                新建
              </Button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {wikiPages.length === 0 && !wikiLoading ? (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card py-12 text-center">
                  <Sparkles className="mb-2 h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">暂无 Wiki 页面</p>
                  <p className="mt-1 text-xs text-muted-foreground">从文档生成或手动创建</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {wikiPages.map((page) => (
                    <div
                      key={page.page_id}
                      className="flex items-start justify-between rounded-lg border border-border bg-card p-3 transition-colors hover:border-accent/30"
                    >
                      <div className="min-w-0 flex-1 cursor-pointer" onClick={() => openWikiPage(page)}>
                        <div className="flex items-center gap-2">
                          <Sparkles className="h-4 w-4 shrink-0 text-accent" />
                          <span className="truncate text-sm font-medium text-foreground">{page.title}</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
                          {page.content.slice(0, 160)}
                          {page.content.length > 160 ? '…' : ''}
                        </p>
                      </div>
                      <div className="ml-2 flex flex-col gap-1">
                        <Button type="button" variant="ghost" size="sm" onClick={() => openWikiPage(page)}>
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button type="button" variant="ghost" size="sm" onClick={() => deleteWikiPage(page)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="ask" className="min-h-0 flex-1">
          <div className="flex h-full flex-col gap-4">
            <form onSubmit={handleAsk} className="flex items-center gap-2">
              <div className="relative flex-1">
                <Bot className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={askQuestion}
                  onChange={(e) => setAskQuestion(e.target.value)}
                  placeholder="向知识库提问…"
                  className="h-9 w-full rounded-md border border-border bg-surface pl-9 pr-3 text-sm text-foreground outline-none focus:border-accent"
                />
              </div>
              <Button type="submit" disabled={asking || !askQuestion.trim()}>
                {asking ? <Loader2 className="h-4 w-4 animate-spin" /> : '提问'}
              </Button>
            </form>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {askResult ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-border bg-card p-4 shadow-card">
                    <div className="mb-2 text-sm font-medium text-foreground">回答</div>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                      {askResult.answer}
                    </div>
                  </div>
                  {askResult.sources.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-medium text-muted-foreground">来源</div>
                      <div className="flex flex-wrap gap-2">
                        {askResult.sources.map((s, idx) => (
                          <span
                            key={`${s.type}-${s.id || idx}`}
                            className="rounded-full border border-border-faint bg-surface px-2 py-0.5 text-[11px] text-foreground"
                          >
                            {s.type === 'wiki' ? '📖' : '📄'} {s.title || s.id || s.type}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card text-center">
                  <Bot className="mb-2 h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">输入问题，基于 Wiki 和文档回答</p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Document detail dialog */}
      <Dialog open={selectedDoc !== null} onOpenChange={(open) => !open && closeDetail()}>
        <DialogContent className="flex max-h-[85vh] w-[92vw] max-w-2xl flex-col gap-0 overflow-hidden bg-card p-0 text-card-foreground">
          <DialogHeader className="border-b border-border px-4 py-3">
            <DialogTitle className="text-sm font-semibold">文档详情</DialogTitle>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {detailLoading && (
              <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载详情中…
              </div>
            )}

            {detailError && (
              <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {detailError}
              </div>
            )}

            {selectedDoc && !detailLoading && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">标题</label>
                  <input
                    type="text"
                    value={editedTitle}
                    onChange={(e) => setEditedTitle(e.target.value)}
                    className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">摘要（可编辑）</label>
                  <textarea
                    value={editedSummary}
                    onChange={(e) => setEditedSummary(e.target.value)}
                    rows={4}
                    className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
                  />
                </div>

                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={closeDetail}>
                    关闭
                  </Button>
                  <Button type="button" size="sm" onClick={saveDetail} disabled={saving}>
                    {saving ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                    保存
                  </Button>
                </div>

                {detail && (detail.chunks?.length ?? 0) === 0 && (detail.entities?.length ?? 0) === 0 && (
                  <div className="rounded-md border border-border-faint bg-surface p-3 text-xs text-muted-foreground">
                    该文档暂无解析片段或实体。
                  </div>
                )}

                {detail && (detail.chunks?.length ?? 0) > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-muted-foreground">
                      片段 ({detail.chunks.length})
                    </div>
                    <div className="space-y-2">
                      {detail.chunks.map((chunk, idx) => (
                        <div
                          key={chunk.id}
                          className="rounded-md border border-border-faint bg-surface p-2.5 text-xs text-foreground"
                        >
                          <div className="mb-1 text-[10px] text-muted-foreground">片段 {idx + 1}</div>
                          <p className="whitespace-pre-wrap leading-relaxed">{chunk.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {detail && (detail.entities?.length ?? 0) > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-muted-foreground">
                      实体 ({detail.entities.length})
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {detail.entities.map((entity) => (
                        <span
                          key={entity.id}
                          className="rounded-full border border-border-faint bg-surface px-2 py-0.5 text-[11px] text-foreground"
                        >
                          {entity.name || entity.id}
                          {entity.type ? ` · ${entity.type}` : ''}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Wiki page dialog */}
      <Dialog open={selectedWikiPage !== null} onOpenChange={(open) => !open && closeWikiPage()}>
        <DialogContent className="flex max-h-[85vh] w-[92vw] max-w-2xl flex-col gap-0 overflow-hidden bg-card p-0 text-card-foreground">
          <DialogHeader className="border-b border-border px-4 py-3">
            <DialogTitle className="text-sm font-semibold">Wiki 页面</DialogTitle>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {selectedWikiPage && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">标题</label>
                  <input
                    type="text"
                    value={wikiEditTitle}
                    onChange={(e) => setWikiEditTitle(e.target.value)}
                    className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">内容（Markdown）</label>
                  <textarea
                    value={wikiEditContent}
                    onChange={(e) => setWikiEditContent(e.target.value)}
                    rows={14}
                    className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm font-mono text-foreground outline-none focus:border-accent"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={closeWikiPage}>
                    关闭
                  </Button>
                  <Button type="button" size="sm" onClick={saveWikiPage} disabled={wikiSaving}>
                    {wikiSaving ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                    保存
                  </Button>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Create wiki page dialog */}
      <Dialog open={showCreateWiki} onOpenChange={(open) => !open && setShowCreateWiki(false)}>
        <DialogContent className="flex max-h-[85vh] w-[92vw] max-w-2xl flex-col gap-0 overflow-hidden bg-card p-0 text-card-foreground">
          <DialogHeader className="border-b border-border px-4 py-3">
            <DialogTitle className="text-sm font-semibold">新建 Wiki 页面</DialogTitle>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">标题</label>
                <input
                  type="text"
                  value={newWikiTitle}
                  onChange={(e) => setNewWikiTitle(e.target.value)}
                  placeholder="页面标题"
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">内容（Markdown）</label>
                <textarea
                  value={newWikiContent}
                  onChange={(e) => setNewWikiContent(e.target.value)}
                  rows={12}
                  placeholder="支持 Markdown"
                  className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm font-mono text-foreground outline-none focus:border-accent"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setShowCreateWiki(false)}>
                  取消
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={createWikiPage}
                  disabled={wikiSaving || !newWikiTitle.trim() || !newWikiContent.trim()}
                >
                  {wikiSaving ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                  创建
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
