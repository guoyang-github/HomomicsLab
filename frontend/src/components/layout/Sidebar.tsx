import { clsx } from 'clsx'
import { useEffect, useState } from 'react'
import {
  MessageSquare,
  FlaskConical,
  FolderOpen,
  Folder,
  Settings,
  Command,
  Plug,
  PanelLeft,
  FolderKanban,
  Plus,
  Loader2,
} from 'lucide-react'
import { useTranslation } from '@/i18n'
import { healthApi } from '@/sdk'
import { useProjectStore } from '@/stores/projectStore'
import { useChatStore } from '@/stores/chatStore'
import { useAnalysisTemplateStore } from '@/stores/analysisTemplateStore'
import { Button, Select, Modal, Input } from '@/components/ui'
import { SidebarSessions } from './SidebarSessions'

export type NavItem = 'chat' | 'files' | 'skills' | 'domains' | 'mcp' | 'settings'

interface SidebarItem {
  id: NavItem
  labelKey: string
  icon: typeof Command
  shortcut?: string
}

const navItems: SidebarItem[] = [
  { id: 'chat', labelKey: 'nav.chat', icon: MessageSquare, shortcut: '⌘1' },
  { id: 'files', labelKey: 'nav.files', icon: Folder, shortcut: '⌘2' },
  { id: 'skills', labelKey: 'nav.skills', icon: FlaskConical, shortcut: '⌘3' },
  { id: 'domains', labelKey: 'nav.domains', icon: FolderOpen, shortcut: '⌘4' },
  { id: 'mcp', labelKey: 'nav.mcp', icon: Plug, shortcut: '⌘5' },
  { id: 'settings', labelKey: 'nav.settings', icon: Settings, shortcut: '⌘6' },
]

interface SidebarProps {
  activeItem: NavItem
  onNavigate: (item: NavItem) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

export function Sidebar({ activeItem, onNavigate, collapsed = false, onToggleCollapse }: SidebarProps) {
  const { t } = useTranslation()
  const [version, setVersion] = useState<string>('')
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null)
  const [llmModel, setLlmModel] = useState<string | null>(null)

  const projects = useProjectStore((state) => state.projects)
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const loadingProjects = useProjectStore((state) => state.loading)
  const projectError = useProjectStore((state) => state.error)
  const fetchProjects = useProjectStore((state) => state.fetchProjects)
  const createProject = useProjectStore((state) => state.createProject)
  const setCurrentProject = useProjectStore((state) => state.setCurrentProject)
  const clearProjectError = useProjectStore((state) => state.clearError)

  const setProjectId = useChatStore((state) => state.setProjectId)
  const clearMessages = useChatStore((state) => state.clearMessages)

  const templates = useAnalysisTemplateStore((state) => state.templates)
  const templatesLoading = useAnalysisTemplateStore((state) => state.loading)
  const fetchTemplates = useAnalysisTemplateStore((state) => state.fetchTemplates)

  const [projectModalOpen, setProjectModalOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDescription, setNewProjectDescription] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    if (projectModalOpen) {
      fetchTemplates()
    }
  }, [projectModalOpen, fetchTemplates])

  useEffect(() => {
    const fetchHealth = () => {
      healthApi
        .getLive()
        .then((res) => {
          const data = res.data
          if (data?.version) {
            setVersion(data.version)
          }
          if (typeof data?.llm_configured === 'boolean') {
            setLlmConfigured(data.llm_configured)
          }
          if (data?.llm_model) {
            setLlmModel(data.llm_model)
          }
        })
        .catch(() => {
          // ignore; keep empty fallback
        })
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 10_000)
    return () => clearInterval(interval)
  }, [])

  const versionLabel = version ? `v${version}` : 'v0.1'
  const llmTooltip = llmConfigured
    ? `LLM connected: ${llmModel ?? 'unknown'}`
    : 'LLM not configured — answers use rule-based fallback and web search.'

  const projectOptions = [
    { value: 'default', label: t('sessionList.defaultProject') },
    ...projects.map((p) => ({ value: p.id, label: p.name })),
  ]

  const currentProjectName =
    currentProjectId === 'default'
      ? t('sessionList.defaultProject')
      : projects.find((p) => p.id === currentProjectId)?.name || currentProjectId

  const handleProjectChange = (value: string) => {
    setCurrentProject(value)
    setProjectId(value)
    clearMessages()
  }

  const handleCreateProject = async () => {
    const name = newProjectName.trim()
    if (!name) return
    setIsCreating(true)
    const project = await createProject(
      name,
      newProjectDescription.trim(),
      selectedTemplateId || undefined
    )
    setIsCreating(false)
    if (project) {
      setNewProjectName('')
      setNewProjectDescription('')
      setSelectedTemplateId('')
      setProjectModalOpen(false)
      setProjectId(project.id)
      clearMessages()
    }
  }

  return (
    <aside
      className={clsx(
        'flex h-full shrink-0 flex-col border-r border-border-faint bg-surface transition-all duration-200',
        collapsed ? 'w-12' : 'w-60'
      )}
    >
      <div
        className={clsx(
          'relative flex shrink-0 items-center border-b border-border-faint',
          collapsed ? 'h-12 justify-between px-1' : 'h-12 justify-between px-3'
        )}
      >
        <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
          <Command className="h-4 w-4" />
          {collapsed && (
            <span
              className={clsx(
                'absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-surface shadow-sm',
                llmConfigured === true && 'bg-green-500',
                llmConfigured === false && 'animate-pulse bg-red-500',
                llmConfigured === null && 'bg-muted-foreground/50'
              )}
              title={llmTooltip}
            />
          )}
        </div>
        {!collapsed && (
          <div className="flex flex-1 flex-col overflow-hidden px-2">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-bold text-foreground">HomomicsLab</span>
              <span
                className={clsx(
                  'h-2.5 w-2.5 shrink-0 rounded-full shadow-sm',
                  llmConfigured === true && 'bg-green-500',
                  llmConfigured === false && 'animate-pulse bg-red-500',
                  llmConfigured === null && 'bg-muted-foreground/50'
                )}
                title={llmTooltip}
              />
            </div>
            <span className="truncate text-[10px] text-muted-foreground">Bioinfo Agent</span>
          </div>
        )}
        <button
          type="button"
          onClick={onToggleCollapse}
          className="rounded p-1 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
          title={collapsed ? t('topbar.expandSidebar') : t('topbar.collapseSidebar')}
        >
          <PanelLeft className={clsx('h-4 w-4', collapsed && 'rotate-180')} />
        </button>
      </div>

      <nav className="shrink-0 space-y-0.5 p-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const label = t(item.labelKey)
          const isActive = activeItem === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={clsx(
                'group flex items-center gap-2.5 rounded-lg py-1.5 text-[13px] font-medium transition-colors',
                collapsed ? 'w-full justify-center px-0' : 'w-full px-2',
                isActive
                  ? 'bg-surface-2 text-accent'
                  : 'text-muted-foreground hover:bg-surface-2/60 hover:text-foreground'
              )}
              title={collapsed ? label : undefined}
            >
              <Icon className={clsx('h-4 w-4 shrink-0', isActive && 'text-accent')} />
              {!collapsed && <span className="flex-1 text-left">{label}</span>}
              {!collapsed && item.shortcut && (
                <kbd className="hidden rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted-foreground group-hover:inline-block">
                  {item.shortcut}
                </kbd>
              )}
            </button>
          )
        })}
      </nav>

      <div className={clsx('shrink-0 border-t border-border-faint p-2', collapsed ? 'mt-0' : 'mt-3')}>
        {collapsed ? (
          <button
            type="button"
            onClick={() => setProjectModalOpen(true)}
            className="flex h-9 w-full items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
            title={currentProjectName}
          >
            <FolderKanban className="h-4 w-4" />
          </button>
        ) : (
          <>
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground">
                <FolderKanban className="h-3 w-3" />
                {t('common.project')}
              </span>
              <button
                type="button"
                onClick={() => setProjectModalOpen(true)}
                className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
                title={t('sessionList.createProject')}
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
            <Select
              value={currentProjectId}
              onChange={(e) => handleProjectChange(e.target.value)}
              options={projectOptions}
              disabled={loadingProjects}
              className="h-8 text-xs"
            />
            {projectError && (
              <div className="mt-2 flex items-center gap-2 rounded-md bg-error/10 px-2 py-1.5">
                <p className="flex-1 text-[11px] leading-tight text-error">{projectError}</p>
                <Button size="sm" variant="ghost" className="h-auto px-2 py-1 text-[11px]" onClick={fetchProjects}>
                  {t('common.retry')}
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      <SidebarSessions collapsed={collapsed} />

      <div className="shrink-0 border-t border-border-faint p-2">
        <div className="flex items-center justify-center gap-2">
          {!collapsed && (
            <div className="rounded-lg bg-surface-2/60 px-2.5 py-1.5 text-[10px] text-muted-foreground">
              HomomicsLab {versionLabel}
            </div>
          )}
        </div>
      </div>

      <Modal
        open={projectModalOpen}
        onClose={() => {
          setProjectModalOpen(false)
          clearProjectError()
          setSelectedTemplateId('')
        }}
        title={t('sessionList.createProject')}
        description={t('sessionList.createProjectDesc')}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setProjectModalOpen(false)
                clearProjectError()
                setSelectedTemplateId('')
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button onClick={handleCreateProject} disabled={isCreating || !newProjectName.trim()}>
              {isCreating && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
              {t('sessionList.create')}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">{t('common.project')}</label>
            <Select
              value={currentProjectId}
              onChange={(e) => handleProjectChange(e.target.value)}
              options={projectOptions}
              disabled={loadingProjects}
            />
          </div>
          <Input
            placeholder={t('sessionList.projectName')}
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
          />
          <Input
            placeholder={t('sessionList.description')}
            value={newProjectDescription}
            onChange={(e) => setNewProjectDescription(e.target.value)}
          />
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('sessionList.analysisTemplate')}
            </label>
            <Select
              value={selectedTemplateId}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
              disabled={templatesLoading}
              options={[
                { value: '', label: t('sessionList.noTemplate') },
                ...templates.map((t) => ({ value: t.template_id, label: t.name })),
              ]}
            />
            {selectedTemplateId && (
              <p className="mt-1 text-xs text-muted-foreground">
                {templates.find((t) => t.template_id === selectedTemplateId)?.description}
              </p>
            )}
          </div>
          {projectError && <p className="text-xs text-error">{projectError}</p>}
        </div>
      </Modal>
    </aside>
  )
}
