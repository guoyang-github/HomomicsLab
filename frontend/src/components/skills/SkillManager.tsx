import { useState, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import {
  Loader2,
  X,
  Lock,
  Play,
  ShieldCheck,
  Trash2,
  Power,
  PowerOff,
  Save,
  Download,
} from 'lucide-react'
import { skillsApi } from '@/services/api'
import type { SkillDetail, SkillTestResponse, SkillValidationResponse } from '@/types/api'
import {
  Button,
  Input,
  Badge,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  EmptyState,
  Select,
} from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'

const categoryColors: Record<string, string> = {
  'single-cell': 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  'spatial-transcriptomics': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  'workflows': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  'genomics': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  'agent_core': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
}

const runtimeColors: Record<string, string> = {
  python: 'border-blue-200 text-blue-600 dark:border-blue-800 dark:text-blue-400',
  r: 'border-green-200 text-green-600 dark:border-green-800 dark:text-green-400',
  mixed: 'border-amber-200 text-amber-600 dark:border-amber-800 dark:text-amber-400',
  cli: 'border-rose-200 text-rose-600 dark:border-rose-800 dark:text-rose-400',
  workflow: 'border-cyan-200 text-cyan-600 dark:border-cyan-800 dark:text-cyan-400',
  container: 'border-violet-200 text-violet-600 dark:border-violet-800 dark:text-violet-400',
}

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
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载 Skills 失败')
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
      toastSuccess('Skill 导入成功')
      await loadSkills()
    } catch (err: any) {
      setError(err?.response?.data?.detail || '导入失败')
      toastError(err?.response?.data?.detail || '导入失败')
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
      toastSuccess(`${skill.name} 已${skill.enabled ? '禁用' : '启用'}`)
      await loadSkills()
    } catch (err: any) {
      toastError(err?.response?.data?.detail || '切换失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleRemove = async (skill: SkillDetail) => {
    if (!confirm(`确定要移除 Skill "${skill.name}" 吗？`)) return
    setActionLoading(skill.id)
    try {
      await skillsApi.removeSkill(skill.id, skill.namespace)
      setSelectedSkill(null)
      toastSuccess('Skill 已移除')
      await loadSkills()
    } catch (err: any) {
      toastError(err?.response?.data?.detail || '移除失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleValidate = async (skill: SkillDetail) => {
    setActionLoading(`${skill.id}:validate`)
    try {
      const response = await skillsApi.validateSkill(skill.id, skill.namespace)
      setValidationResult(response.data)
      toastSuccess(response.data.valid ? '验证通过' : '验证未通过')
    } catch (err: any) {
      toastError(err?.response?.data?.detail || '验证失败')
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
      toastSuccess(response.data.success ? '测试通过' : '测试失败')
    } catch (err: any) {
      toastError(err?.response?.data?.detail || '测试失败')
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
      toastSuccess('版本已锁定')
    } catch (err: any) {
      toastError(err?.response?.data?.detail || '锁定失败')
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
      toastSuccess('CodeAct 运行已升级为 Skill')
      await loadSkills()
    } catch (err: any) {
      setError(err?.response?.data?.detail || '升级失败')
      toastError(err?.response?.data?.detail || '升级失败')
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-card px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Skill 管理</h2>
          <Button onClick={handleLock} loading={actionLoading === 'lock'} variant="secondary">
            <Lock className="mr-1.5 h-4 w-4" />
            锁定版本
          </Button>
        </div>

        <div className="flex gap-2">
          <Input
            value={importSource}
            onChange={(e) => setImportSource(e.target.value)}
            placeholder="路径、Git URL 或 zip 压缩包..."
            className="flex-1"
          />
          <Input
            value={importNamespace}
            onChange={(e) => setImportNamespace(e.target.value)}
            placeholder="命名空间"
            className="w-32"
          />
          <Button onClick={handleImport} loading={actionLoading === 'import'} disabled={!importSource.trim()}>
            导入
          </Button>
        </div>

        <Card className="mt-3">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">将 CodeAct 运行升级为 Skill</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={promoteSourceDir}
              onChange={(e) => setPromoteSourceDir(e.target.value)}
              placeholder="CodeAct 工作目录路径..."
              className="flex-1"
            />
            <Input
              value={promoteName}
              onChange={(e) => setPromoteName(e.target.value)}
              placeholder="Skill 名称（可选）"
              className="w-48"
            />
            <Select
              value={promoteCategory}
              options={[
                { value: 'generated', label: 'Generated' },
                { value: 'single-cell', label: 'Single Cell' },
                { value: 'spatial-transcriptomics', label: 'Spatial' },
                { value: 'genomics', label: 'Genomics' },
                { value: 'workflows', label: 'Workflows' },
              ]}
              onChange={(e) => setPromoteCategory(e.target.value)}
              className="w-40"
            />
            <Button
              onClick={handlePromote}
              loading={actionLoading === 'promote'}
              disabled={!promoteSourceDir.trim()}
              className="bg-success hover:bg-success-700"
            >
              <Save className="mr-1.5 h-4 w-4" />
              保存为 Skill
            </Button>
          </CardContent>
        </Card>

        {error && <p className="mt-2 text-xs text-error">{error}</p>}
        {lockResult && (
          <pre className="mt-2 max-h-32 overflow-auto rounded-lg bg-muted p-3 text-xs">{lockResult}</pre>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className={clsx('overflow-y-auto border-r border-border', selectedSkill ? 'w-1/2' : 'w-full')}>
          {loading && skills.length === 0 && (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {!loading && skills.length === 0 && (
            <EmptyState
              icon={Download}
              title="暂无 Skills"
              description="导入或启用 Skills 以开始使用"
              action={{ label: '刷新', onClick: loadSkills }}
            />
          )}

          <div className="divide-y divide-border">
            {skills.map((skill) => (
              <button
                key={`${skill.namespace}:${skill.id}`}
                onClick={() => {
                  setSelectedSkill(skill)
                  setTestResult(null)
                  setValidationResult(null)
                }}
                className={clsx(
                  'w-full px-4 py-3 text-left transition-colors hover:bg-muted/50',
                  selectedSkill?.id === skill.id && selectedSkill?.namespace === skill.namespace
                    ? 'bg-primary/5 ring-1 ring-inset ring-primary/20'
                    : ''
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-foreground">{skill.name}</span>
                      <Badge className={categoryColors[skill.category] || 'bg-slate-100 text-slate-600'} size="sm">
                        {skill.category}
                      </Badge>
                      {!skill.enabled && <Badge variant="secondary" size="sm">已禁用</Badge>}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{skill.description}</p>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge variant="outline" className={runtimeColors[skill.runtime_type]} size="sm">
                    {skill.runtime_type.toUpperCase()}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{skill.namespace}</span>
                  <span className="text-xs text-muted-foreground">v{skill.version}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {selectedSkill && (
          <div className="w-1/2 overflow-y-auto bg-muted/30 p-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-foreground">{selectedSkill.name}</h3>
                <p className="text-xs text-muted-foreground">{selectedSkill.namespace} / {selectedSkill.id}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setSelectedSkill(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mb-4 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={selectedSkill.enabled ? 'outline' : 'default'}
                onClick={() => handleToggle(selectedSkill)}
                loading={actionLoading === selectedSkill.id}
              >
                {selectedSkill.enabled ? <PowerOff className="mr-1.5 h-3.5 w-3.5" /> : <Power className="mr-1.5 h-3.5 w-3.5" />}
                {selectedSkill.enabled ? '禁用' : '启用'}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleValidate(selectedSkill)}
                loading={actionLoading === `${selectedSkill.id}:validate`}
              >
                <ShieldCheck className="mr-1.5 h-3.5 w-3.5" />
                验证
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleTest(selectedSkill)}
                loading={actionLoading === `${selectedSkill.id}:test`}
              >
                <Play className="mr-1.5 h-3.5 w-3.5" />
                测试
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => handleRemove(selectedSkill)}
                loading={actionLoading === selectedSkill.id}
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                移除
              </Button>
            </div>

            {validationResult && (
              <Card className={clsx('mb-4', validationResult.valid ? 'border-success/30' : 'border-error/30')}>
                <CardContent className="py-3">
                  <div className={clsx('text-sm font-medium', validationResult.valid ? 'text-success' : 'text-error')}>
                    {validationResult.valid ? '验证通过' : '验证失败'}
                  </div>
                  {validationResult.errors.length > 0 && (
                    <ul className="mt-2 list-inside list-disc text-xs text-error">
                      {validationResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  )}
                  {validationResult.warnings.length > 0 && (
                    <ul className="mt-2 list-inside list-disc text-xs text-warning">
                      {validationResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  )}
                </CardContent>
              </Card>
            )}

            {testResult && (
              <Card className={clsx('mb-4', testResult.success ? 'border-success/30' : 'border-error/30')}>
                <CardContent className="py-3">
                  <div className={clsx('text-sm font-medium', testResult.success ? 'text-success' : 'text-error')}>
                    {testResult.success ? '测试通过' : '测试失败'}
                    {testResult.tests_run > 0 && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        {testResult.tests_passed}/{testResult.tests_run}
                      </span>
                    )}
                  </div>
                  {testResult.stdout && (
                    <pre className="mt-2 max-h-32 overflow-auto rounded-lg bg-muted p-2 text-xs">{testResult.stdout}</pre>
                  )}
                  {testResult.stderr && (
                    <pre className="mt-2 max-h-32 overflow-auto rounded-lg bg-error/10 p-2 text-xs text-error">{testResult.stderr}</pre>
                  )}
                </CardContent>
              </Card>
            )}

            <div className="space-y-3 rounded-lg border border-border bg-card p-4 text-sm">
              <InfoRow label="版本" value={selectedSkill.version} />
              <InfoRow label="来源" value={selectedSkill.source} />
              <InfoRow label="运行时" value={selectedSkill.runtime_type} />
              <InfoRow label="主要工具" value={selectedSkill.primary_tool || 'N/A'} />
              {selectedSkill.dependencies.length > 0 && (
                <InfoRow label="依赖" value={selectedSkill.dependencies.join(', ')} />
              )}
              {selectedSkill.keywords.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-muted-foreground">关键词</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {selectedSkill.keywords.map((k, idx) => (
                      <Badge key={`${k}-${idx}`} variant="secondary" size="sm">{k}</Badge>
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

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="mt-0.5 text-foreground">{value}</div>
    </div>
  )
}
