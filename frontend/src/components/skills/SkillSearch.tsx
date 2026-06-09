import { useState, useEffect, useCallback, useRef } from 'react'
import { skillsApi } from '@/services/api'
import type { SkillSummary, SkillDetail } from '@/types/api'

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
    } catch (err) {
      setError('Failed to load skills')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAllSkills()
  }, [loadAllSkills])

  const handleSearch = (value: string) => {
    setQuery(value)

    if (searchTimeout.current) {
      clearTimeout(searchTimeout.current)
    }

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
      } catch (err) {
        setError('Search failed')
        console.error(err)
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
    } catch (err) {
      console.error('Failed to load skill detail:', err)
    } finally {
      setDetailLoading(false)
    }
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'single-cell': 'bg-purple-100 text-purple-700',
      'spatial-transcriptomics': 'bg-emerald-100 text-emerald-700',
      'workflows': 'bg-blue-100 text-blue-700',
      'genomics': 'bg-amber-100 text-amber-700',
      'proteomics': 'bg-rose-100 text-rose-700',
    }
    return colors[category] || 'bg-slate-100 text-slate-600'
  }

  const getRuntimeBadge = (runtimeType: string) => {
    const colors: Record<string, string> = {
      python: 'bg-blue-50 text-blue-600 border-blue-200',
      r: 'bg-green-50 text-green-600 border-green-200',
      mixed: 'bg-amber-50 text-amber-600 border-amber-200',
    }
    return colors[runtimeType] || 'bg-slate-50 text-slate-600 border-slate-200'
  }

  return (
    <div className="flex h-full flex-col">
      {/* Search header */}
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search skills (e.g., UMAP, Seurat, QC)..."
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <span className="absolute left-3 top-2.5 text-slate-400">🔍</span>
          {query && (
            <button
              onClick={() => { setQuery(''); loadAllSkills(); }}
              className="absolute right-3 top-2 text-slate-400 hover:text-slate-600"
            >
              ✕
            </button>
          )}
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
          <span>{skills.length} skills found</span>
          {query && <span className="text-primary">Searching: "{query}"</span>}
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Skills list */}
        <div className={`${selectedSkill ? 'w-1/2' : 'w-full'} overflow-y-auto border-r border-slate-200`}>
          {loading && skills.length === 0 && (
            <div className="flex h-full items-center justify-center">
              <div className="text-sm text-slate-500">Loading skills...</div>
            </div>
          )}

          {error && (
            <div className="flex h-full flex-col items-center justify-center gap-2 p-4">
              <div className="text-sm text-red-500">{error}</div>
              <button
                onClick={loadAllSkills}
                className="rounded bg-primary px-3 py-1 text-xs text-white hover:bg-primary/90"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && skills.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center p-4 text-center">
              <div className="mb-2 text-3xl">🔧</div>
              <div className="text-sm font-medium text-slate-700">No skills found</div>
              <div className="mt-1 text-xs text-slate-500">Try a different search term</div>
            </div>
          )}

          <div className="divide-y divide-slate-100">
            {skills.map((skill) => (
              <button
                key={skill.id}
                onClick={() => handleSelectSkill(skill.id)}
                className={`w-full px-4 py-3 text-left transition-colors hover:bg-slate-50 ${
                  selectedSkill?.id === skill.id ? 'bg-blue-50 ring-1 ring-inset ring-blue-200' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-800">{skill.name}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getCategoryColor(skill.category)}`}>
                        {skill.category}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">{skill.description}</p>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`rounded border px-1.5 py-0.5 text-xs font-medium ${getRuntimeBadge(skill.runtime_type)}`}>
                    {skill.runtime_type.toUpperCase()}
                  </span>
                  {skill.primary_tool && (
                    <span className="text-xs text-slate-400">
                      {skill.primary_tool}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        {selectedSkill && (
          <div className="w-1/2 overflow-y-auto bg-slate-50">
            {detailLoading ? (
              <div className="flex h-full items-center justify-center">
                <div className="text-sm text-slate-500">Loading detail...</div>
              </div>
            ) : (
              <div className="p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-slate-800">{selectedSkill.name}</h3>
                  <button
                    onClick={() => setSelectedSkill(null)}
                    className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
                  >
                    ✕
                  </button>
                </div>

                <p className="mb-4 text-sm text-slate-600">{selectedSkill.description}</p>

                <div className="space-y-3">
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Category</div>
                    <div className="mt-1 text-sm text-slate-800">{selectedSkill.category}</div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Runtime</div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className={`rounded border px-2 py-0.5 text-xs font-medium ${getRuntimeBadge(selectedSkill.runtime_type)}`}>
                        {selectedSkill.runtime_type.toUpperCase()}
                      </span>
                      {selectedSkill.primary_tool && (
                        <span className="text-sm text-slate-600">Primary: {selectedSkill.primary_tool}</span>
                      )}
                    </div>
                  </div>

                  {selectedSkill.keywords.length > 0 && (
                    <div className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Keywords</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedSkill.keywords.map((kw) => (
                          <span key={kw} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedSkill.supported_tools.length > 0 && (
                    <div className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Supported Tools</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedSkill.supported_tools.map((tool) => (
                          <span key={tool} className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedSkill.dependencies.length > 0 && (
                    <div className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Dependencies</div>
                      <div className="mt-1 text-sm text-slate-600">
                        {selectedSkill.dependencies.join(', ')}
                      </div>
                    </div>
                  )}

                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Source</div>
                    <div className="mt-1 text-sm text-slate-600">{selectedSkill.source}</div>
                    <div className="mt-1 text-xs text-slate-400">Version: {selectedSkill.version}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
