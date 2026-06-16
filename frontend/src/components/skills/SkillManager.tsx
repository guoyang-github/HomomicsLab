import { useState, useEffect, useCallback } from 'react'
import { skillsApi } from '@/services/api'
import type { SkillDetail, SkillTestResponse, SkillValidationResponse } from '@/types/api'

export function SkillManager() {
  const [skills, setSkills] = useState<SkillDetail[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedSkill, setSelectedSkill] = useState<SkillDetail | null>(null)
  const [importSource, setImportSource] = useState('')
  const [importNamespace, setImportNamespace] = useState('default')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<SkillTestResponse | null>(null)
  const [validationResult, setValidationResult] = useState<SkillValidationResponse | null>(null)
  const [lockResult, setLockResult] = useState<string>('')
  const [promoteSourceDir, setPromoteSourceDir] = useState('')
  const [promoteName, setPromoteName] = useState('')
  const [promoteCategory, setPromoteCategory] = useState('generated')

  const loadSkills = useCallback(async () => {
    try {
      setLoading(true)
      const response = await skillsApi.listSkills()
      setSkills(response.data as SkillDetail[])
      setError('')
    } catch (err) {
      setError('Failed to load skills')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSkills()
  }, [loadSkills])

  const handleImport = async () => {
    if (!importSource.trim()) return
    setActionLoading('import')
    setError('')
    try {
      await skillsApi.importSkill({
        source: importSource.trim(),
        namespace: importNamespace.trim() || 'default',
        enable: true,
      })
      setImportSource('')
      await loadSkills()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Import failed')
    } finally {
      setActionLoading(null)
    }
  }

  const handleToggle = async (skill: SkillDetail) => {
    setActionLoading(skill.id)
    try {
      if (skill.enabled) {
        await skillsApi.disableSkill(skill.id, skill.namespace)
      } else {
        await skillsApi.enableSkill(skill.id, skill.namespace)
      }
      await loadSkills()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Toggle failed')
    } finally {
      setActionLoading(null)
    }
  }

  const handleRemove = async (skill: SkillDetail) => {
    if (!confirm(`Remove skill "${skill.name}" from namespace "${skill.namespace}"?`)) return
    setActionLoading(skill.id)
    try {
      await skillsApi.removeSkill(skill.id, skill.namespace)
      setSelectedSkill(null)
      await loadSkills()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Remove failed')
    } finally {
      setActionLoading(null)
    }
  }

  const handleValidate = async (skill: SkillDetail) => {
    setActionLoading(`${skill.id}:validate`)
    try {
      const response = await skillsApi.validateSkill(skill.id, skill.namespace)
      setValidationResult(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Validation failed')
    } finally {
      setActionLoading(null)
    }
  }

  const handleTest = async (skill: SkillDetail) => {
    setActionLoading(`${skill.id}:test`)
    setTestResult(null)
    try {
      const response = await skillsApi.testSkill(skill.id, skill.namespace)
      setTestResult(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Test failed')
    } finally {
      setActionLoading(null)
    }
  }

  const handleLock = async () => {
    setActionLoading('lock')
    try {
      const projectId = prompt('Project ID for lock file:', 'default-project') || 'default-project'
      const response = await skillsApi.lockSkills(projectId)
      setLockResult(JSON.stringify(response.data, null, 2))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Lock failed')
    } finally {
      setActionLoading(null)
    }
  }

  const handlePromote = async () => {
    if (!promoteSourceDir.trim()) return
    setActionLoading('promote')
    setError('')
    try {
      await skillsApi.promoteSkill({
        source_dir: promoteSourceDir.trim(),
        name: promoteName.trim() || undefined,
        category: promoteCategory.trim() || 'generated',
      })
      setPromoteSourceDir('')
      setPromoteName('')
      await loadSkills()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Promotion failed')
    } finally {
      setActionLoading(null)
    }
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'single-cell': 'bg-purple-100 text-purple-700',
      'spatial-transcriptomics': 'bg-emerald-100 text-emerald-700',
      'workflows': 'bg-blue-100 text-blue-700',
      'genomics': 'bg-amber-100 text-amber-700',
      'agent_core': 'bg-indigo-100 text-indigo-700',
    }
    return colors[category] || 'bg-slate-100 text-slate-600'
  }

  const getRuntimeBadge = (runtimeType: string) => {
    const colors: Record<string, string> = {
      python: 'bg-blue-50 text-blue-600 border-blue-200',
      r: 'bg-green-50 text-green-600 border-green-200',
      mixed: 'bg-amber-50 text-amber-600 border-amber-200',
      cli: 'bg-rose-50 text-rose-600 border-rose-200',
      workflow: 'bg-cyan-50 text-cyan-600 border-cyan-200',
      container: 'bg-violet-50 text-violet-600 border-violet-200',
    }
    return colors[runtimeType] || 'bg-slate-50 text-slate-600 border-slate-200'
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">Skill Management</h2>
          <button
            onClick={handleLock}
            disabled={actionLoading === 'lock'}
            className="rounded bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-50"
          >
            {actionLoading === 'lock' ? 'Locking...' : 'Lock Versions'}
          </button>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={importSource}
            onChange={(e) => setImportSource(e.target.value)}
            placeholder="Path, git URL, or zip archive..."
            className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <input
            type="text"
            value={importNamespace}
            onChange={(e) => setImportNamespace(e.target.value)}
            placeholder="Namespace"
            className="w-32 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <button
            onClick={handleImport}
            disabled={actionLoading === 'import' || !importSource.trim()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
          >
            {actionLoading === 'import' ? 'Importing...' : 'Import'}
          </button>
        </div>

        <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 text-xs font-medium text-slate-700">Promote CodeAct run to skill</div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={promoteSourceDir}
              onChange={(e) => setPromoteSourceDir(e.target.value)}
              placeholder="CodeAct workdir path (contains __code_act_source__.py)..."
              className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
            <input
              type="text"
              value={promoteName}
              onChange={(e) => setPromoteName(e.target.value)}
              placeholder="Skill name (optional)"
              className="w-40 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
            <select
              value={promoteCategory}
              onChange={(e) => setPromoteCategory(e.target.value)}
              className="w-36 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary"
            >
              <option value="generated">Generated</option>
              <option value="single-cell">Single Cell</option>
              <option value="spatial-transcriptomics">Spatial</option>
              <option value="genomics">Genomics</option>
              <option value="workflows">Workflows</option>
            </select>
            <button
              onClick={handlePromote}
              disabled={actionLoading === 'promote' || !promoteSourceDir.trim()}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {actionLoading === 'promote' ? 'Promoting...' : 'Save as Skill'}
            </button>
          </div>
        </div>

        {error && <div className="mt-2 text-xs text-red-500">{error}</div>}
        {lockResult && (
          <pre className="mt-2 max-h-32 overflow-auto rounded bg-slate-50 p-2 text-xs text-slate-700">
            {lockResult}
          </pre>
        )}
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

          {!loading && skills.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center p-4 text-center">
              <div className="mb-2 text-3xl">🔧</div>
              <div className="text-sm font-medium text-slate-700">No skills found</div>
              <div className="mt-1 text-xs text-slate-500">Import or enable skills to get started</div>
            </div>
          )}

          <div className="divide-y divide-slate-100">
            {skills.map((skill) => (
              <button
                key={`${skill.namespace}:${skill.id}`}
                onClick={() => {
                  setSelectedSkill(skill)
                  setTestResult(null)
                  setValidationResult(null)
                }}
                className={`w-full px-4 py-3 text-left transition-colors hover:bg-slate-50 ${
                  selectedSkill?.id === skill.id && selectedSkill?.namespace === skill.namespace
                    ? 'bg-blue-50 ring-1 ring-inset ring-blue-200'
                    : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-800">{skill.name}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getCategoryColor(skill.category)}`}>
                        {skill.category}
                      </span>
                      {!skill.enabled && (
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">disabled</span>
                      )}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">{skill.description}</p>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`rounded border px-1.5 py-0.5 text-xs font-medium ${getRuntimeBadge(skill.runtime_type)}`}>
                    {skill.runtime_type.toUpperCase()}
                  </span>
                  <span className="text-xs text-slate-400">{skill.namespace}</span>
                  <span className="text-xs text-slate-400">v{skill.version}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        {selectedSkill && (
          <div className="w-1/2 overflow-y-auto bg-slate-50 p-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-800">{selectedSkill.name}</h3>
                <div className="mt-1 text-xs text-slate-500">{selectedSkill.namespace} / {selectedSkill.id}</div>
              </div>
              <button
                onClick={() => setSelectedSkill(null)}
                className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="mb-4 flex flex-wrap gap-2">
              <button
                onClick={() => handleToggle(selectedSkill)}
                disabled={actionLoading === selectedSkill.id}
                className={`rounded px-3 py-1.5 text-xs font-medium ${
                  selectedSkill.enabled
                    ? 'bg-amber-50 text-amber-600 hover:bg-amber-100'
                    : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
                } disabled:opacity-50`}
              >
                {actionLoading === selectedSkill.id
                  ? 'Working...'
                  : selectedSkill.enabled
                  ? 'Disable'
                  : 'Enable'}
              </button>
              <button
                onClick={() => handleValidate(selectedSkill)}
                disabled={actionLoading === `${selectedSkill.id}:validate`}
                className="rounded bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-100 disabled:opacity-50"
              >
                Validate
              </button>
              <button
                onClick={() => handleTest(selectedSkill)}
                disabled={actionLoading === `${selectedSkill.id}:test`}
                className="rounded bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-600 hover:bg-purple-100 disabled:opacity-50"
              >
                Test
              </button>
              <button
                onClick={() => handleRemove(selectedSkill)}
                disabled={actionLoading === selectedSkill.id}
                className="rounded bg-red-50 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
              >
                Remove
              </button>
            </div>

            {validationResult && (
              <div className="mb-4 rounded border border-slate-200 bg-white p-3">
                <div className={`text-sm font-medium ${validationResult.valid ? 'text-emerald-600' : 'text-red-600'}`}>
                  {validationResult.valid ? 'Valid' : 'Invalid'}
                </div>
                {validationResult.errors.length > 0 && (
                  <ul className="mt-2 list-inside list-disc text-xs text-red-600">
                    {validationResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                )}
                {validationResult.warnings.length > 0 && (
                  <ul className="mt-2 list-inside list-disc text-xs text-amber-600">
                    {validationResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                )}
              </div>
            )}

            {testResult && (
              <div className="mb-4 rounded border border-slate-200 bg-white p-3">
                <div className={`text-sm font-medium ${testResult.success ? 'text-emerald-600' : 'text-red-600'}`}>
                  {testResult.success ? 'Tests passed' : 'Tests failed'}
                  {testResult.tests_run > 0 && (
                    <span className="ml-2 text-xs text-slate-500">
                      {testResult.tests_passed}/{testResult.tests_run}
                    </span>
                  )}
                </div>
                {testResult.stdout && (
                  <pre className="mt-2 max-h-32 overflow-auto rounded bg-slate-50 p-2 text-xs text-slate-700">
                    {testResult.stdout}
                  </pre>
                )}
                {testResult.stderr && (
                  <pre className="mt-2 max-h-32 overflow-auto rounded bg-slate-50 p-2 text-xs text-red-700">
                    {testResult.stderr}
                  </pre>
                )}
              </div>
            )}

            <div className="space-y-3 rounded border border-slate-200 bg-white p-3 text-sm">
              <div>
                <span className="text-xs font-medium text-slate-500">Version</span>
                <div className="text-slate-800">{selectedSkill.version}</div>
              </div>
              <div>
                <span className="text-xs font-medium text-slate-500">Source</span>
                <div className="text-slate-800">{selectedSkill.source}</div>
              </div>
              <div>
                <span className="text-xs font-medium text-slate-500">Runtime</span>
                <div className="text-slate-800">{selectedSkill.runtime_type}</div>
              </div>
              <div>
                <span className="text-xs font-medium text-slate-500">Primary Tool</span>
                <div className="text-slate-800">{selectedSkill.primary_tool || 'N/A'}</div>
              </div>
              {selectedSkill.dependencies.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-slate-500">Dependencies</span>
                  <div className="text-slate-800">{selectedSkill.dependencies.join(', ')}</div>
                </div>
              )}
              {selectedSkill.keywords.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-slate-500">Keywords</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedSkill.keywords.map((k) => (
                      <span key={k} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
