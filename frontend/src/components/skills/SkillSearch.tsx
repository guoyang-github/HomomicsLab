import { useState, useEffect, useCallback, useRef } from 'react'
import { clsx } from 'clsx'
import { Search, X, Loader2, Code2, Tags, Box } from 'lucide-react'
import { skillsApi } from '@/services/api'
import type { SkillSummary, SkillDetail } from '@/types/api'
import { Input, Badge, Button, EmptyState, Skeleton } from '@/components/ui'

const categoryColors: Record<string, string> = {
  'single-cell': 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  'spatial-transcriptomics': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  'workflows': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  'genomics': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  'proteomics': 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
}

const runtimeColors: Record<string, string> = {
  python: 'border-blue-200 text-blue-600 dark:border-blue-800 dark:text-blue-400',
  r: 'border-green-200 text-green-600 dark:border-green-800 dark:text-green-400',
  mixed: 'border-amber-200 text-amber-600 dark:border-amber-800 dark:text-amber-400',
}

export function SkillSearch() {
  const [query, setQuery] = useState('')
  const [skills, setSkills] = useState<SkillSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedSkill, setSelectedSkill] = useState<SkillDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadAllSkills = useCallback(async () => {
    try {
      setLoading(true)
      const response = await skillsApi.listSkills()
      setSkills(response.data)
      setError('')
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载 Skills 失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAllSkills()
  }, [loadAllSkills])

  const handleSearch = (value: string) => {
    setQuery(value)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)

    if (!value.trim()) {
      loadAllSkills()
      return
    }

    searchTimeout.current = setTimeout(async () => {
      try {
        setLoading(true)
        const response = await skillsApi.searchSkills(value.trim())
        setSkills(response.data)
        setError('')
      } catch (err: any) {
        setError(err?.response?.data?.detail || '搜索失败')
      } finally {
        setLoading(false)
      }
    }, 300)
  }

  const handleSelectSkill = async (skillId: string) => {
    try {
      setDetailLoading(true)
      const response = await skillsApi.getSkill(skillId)
      setSelectedSkill(response.data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-card px-4 py-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="搜索 Skills（如 UMAP、Seurat、QC）..."
            className="pl-9 pr-9"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); loadAllSkills(); }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <span>{skills.length} 个 Skills</span>
          {query && <span className="text-primary">搜索："{query}"</span>}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className={clsx('overflow-y-auto border-r border-border', selectedSkill ? 'w-1/2' : 'w-full')}>
          {loading && skills.length === 0 && (
            <div className="space-y-3 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="rounded-lg border border-border p-4">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="mt-2 h-3 w-3/4" />
                </div>
              ))}
            </div>
          )}

          {error && !loading && (
            <div className="flex h-full flex-col items-center justify-center gap-2 p-4">
              <p className="text-sm text-error">{error}</p>
              <Button onClick={loadAllSkills} size="sm">重试</Button>
            </div>
          )}

          {!loading && skills.length === 0 && !error && (
            <EmptyState
              icon={Search}
              title="未找到 Skills"
              description="尝试其他关键词，或在管理页面导入 Skills"
              action={{ label: '刷新', onClick: loadAllSkills }}
            />
          )}

          <div className="divide-y divide-border">
            {skills.map((skill) => (
              <button
                key={skill.id}
                onClick={() => handleSelectSkill(skill.id)}
                className={clsx(
                  'w-full px-4 py-3 text-left transition-colors hover:bg-muted/50',
                  selectedSkill?.id === skill.id && 'bg-primary/5 ring-1 ring-inset ring-primary/20'
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-foreground">{skill.name}</span>
                      <Badge className={categoryColors[skill.category] || 'bg-slate-100 text-slate-600'} size="sm">
                        {skill.category}
                      </Badge>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{skill.description}</p>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge variant="outline" className={runtimeColors[skill.runtime_type]} size="sm">
                    {skill.runtime_type.toUpperCase()}
                  </Badge>
                  {skill.primary_tool && (
                    <span className="text-xs text-muted-foreground">{skill.primary_tool}</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {selectedSkill && (
          <div className="w-1/2 overflow-y-auto bg-muted/30">
            {detailLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="p-4">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">{selectedSkill.name}</h3>
                    <p className="text-xs text-muted-foreground">{selectedSkill.id} · v{selectedSkill.version}</p>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => setSelectedSkill(null)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <p className="mb-4 text-sm text-muted-foreground">{selectedSkill.description}</p>

                <div className="space-y-3">
                  <DetailCard icon={Tags} title="分类" value={selectedSkill.category} />
                  <DetailCard icon={Box} title="运行时" value={selectedSkill.runtime_type.toUpperCase()} />
                  {selectedSkill.primary_tool && (
                    <DetailCard icon={Code2} title="主要工具" value={selectedSkill.primary_tool} />
                  )}
                  {selectedSkill.keywords.length > 0 && (
                    <div className="rounded-lg border border-border bg-card p-3">
                      <div className="text-xs font-semibold uppercase text-muted-foreground">关键词</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedSkill.keywords.map((kw, idx) => (
                          <Badge key={`${kw}-${idx}`} variant="secondary" size="sm">{kw}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedSkill.supported_tools.length > 0 && (
                    <div className="rounded-lg border border-border bg-card p-3">
                      <div className="text-xs font-semibold uppercase text-muted-foreground">支持工具</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedSkill.supported_tools.map((tool, idx) => (
                          <Badge key={`${tool}-${idx}`} variant="outline" size="sm">{tool}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedSkill.dependencies.length > 0 && (
                    <DetailCard icon={Code2} title="依赖" value={selectedSkill.dependencies.join(', ')} />
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function DetailCard({ icon: Icon, title, value }: { icon: React.ElementType; title: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </div>
      <div className="mt-1 text-sm text-foreground">{value}</div>
    </div>
  )
}
