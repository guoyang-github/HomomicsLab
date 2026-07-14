import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import {
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  MessageSquare,
  Loader2,
  FolderKanban,
} from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useProjectStore } from '@/stores/projectStore'
import { Button, Select, Modal, Input } from '@/components/ui'
import { useTranslation } from '@/i18n'
import { useAnalysisTemplateStore } from '@/stores/analysisTemplateStore'

interface Props {
  collapsed?: boolean
}

export function SidebarSessions({ collapsed = false }: Props) {
  const { t } = useTranslation()

  const sessions = useChatStore((state) => state.sessions)
  const sessionsLoading = useChatStore((state) => state.sessionsLoading)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const selectSession = useChatStore((state) => state.selectSession)
  const createSession = useChatStore((state) => state.createSession)
  const renameSession = useChatStore((state) => state.renameSession)
  const deleteSession = useChatStore((state) => state.deleteSession)
  const clearMessages = useChatStore((state) => state.clearMessages)
  const setProjectId = useChatStore((state) => state.setProjectId)
  const fetchSessions = useChatStore((state) => state.fetchSessions)

  const projects = useProjectStore((state) => state.projects)
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const loadingProjects = useProjectStore((state) => state.loading)
  const projectError = useProjectStore((state) => state.error)
  const fetchProjects = useProjectStore((state) => state.fetchProjects)
  const createProject = useProjectStore((state) => state.createProject)
  const setCurrentProject = useProjectStore((state) => state.setCurrentProject)
  const clearProjectError = useProjectStore((state) => state.clearError)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDescription, setNewProjectDescription] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [isCreating, setIsCreating] = useState(false)

  const templates = useAnalysisTemplateStore((state) => state.templates)
  const templatesLoading = useAnalysisTemplateStore((state) => state.loading)
  const fetchTemplates = useAnalysisTemplateStore((state) => state.fetchTemplates)

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    fetchSessions(currentProjectId)
  }, [currentProjectId, fetchSessions])

  useEffect(() => {
    if (isCreateModalOpen) {
      fetchTemplates()
    }
  }, [isCreateModalOpen, fetchTemplates])

  useEffect(() => {
    if (sessionsLoading) return
    const projectSessions = sessions.filter((s) => s.projectId === currentProjectId)
    if (projectSessions.length === 0) {
      createSession(t('sessionList.defaultSession'), currentProjectId)
      return
    }
    if (!projectSessions.some((s) => s.id === currentSessionId)) {
      selectSession(projectSessions[0].id)
    }
  }, [currentProjectId, sessions, currentSessionId, createSession, selectSession, t, sessionsLoading])

  if (collapsed) return null

  const projectSessions = sessions.filter((s) => s.projectId === currentProjectId)

  const startEdit = (id: string, name: string) => {
    setEditingId(id)
    setEditName(name)
  }

  const saveEdit = () => {
    if (editingId && editName.trim()) {
      renameSession(editingId, editName.trim())
    }
    setEditingId(null)
  }

  const handleDelete = (id: string) => {
    if (confirm(t('sessionList.deleteConfirm'))) {
      deleteSession(id)
    }
  }

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
      setIsCreateModalOpen(false)
      setProjectId(project.id)
      clearMessages()
    }
  }

  const projectOptions = [
    { value: 'default', label: t('sessionList.defaultProject') },
    ...projects.map((p) => ({ value: p.id, label: p.name })),
  ]

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-t border-border-faint px-3 py-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            <FolderKanban className="h-3 w-3" />
            {t('common.project')}
          </span>
          <button
            type="button"
            onClick={() => setIsCreateModalOpen(true)}
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
        />
        {projectError && (
          <div className="mt-2 flex items-center gap-2 rounded-md bg-error/10 px-2 py-1.5">
            <p className="flex-1 text-[11px] leading-tight text-error">{projectError}</p>
            <Button size="sm" variant="ghost" className="h-auto px-2 py-1 text-[11px]" onClick={fetchProjects}>
              {t('common.retry')}
            </Button>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-border-faint px-3 py-2">
        <span className="px-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {t('sessionList.sessions')}
        </span>
        <button
          type="button"
          onClick={() => createSession(undefined, currentProjectId)}
          className="rounded p-1 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
          title={t('sessionList.new')}
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {sessionsLoading ? (
          <div className="flex items-center justify-center p-4 text-xs text-muted-foreground">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            {t('common.loading')}
          </div>
        ) : projectSessions.length === 0 ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">{t('sessionList.noSessions')}</div>
        ) : (
          <div className="space-y-0.5">
            {projectSessions.map((session) => {
              const isActive = session.id === currentSessionId
              const isEditing = editingId === session.id

              return (
                <div
                  key={session.id}
                  className={clsx(
                    'group flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors',
                    isActive ? 'bg-surface-2 text-foreground' : 'text-muted-foreground hover:bg-surface-2/60 hover:text-foreground'
                  )}
                >
                  <MessageSquare
                    className={clsx('h-3.5 w-3.5 shrink-0', isActive ? 'text-accent' : 'text-muted-foreground/70')}
                  />

                  {isEditing ? (
                    <div className="flex flex-1 items-center gap-1">
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit()
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        autoFocus
                        className="h-6 flex-1 rounded border border-border bg-surface px-1.5 text-xs"
                      />
                      <button
                        type="button"
                        onClick={saveEdit}
                        className="rounded p-0.5 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                      >
                        <Check className="h-3 w-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="rounded p-0.5 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => selectSession(session.id)}
                      className="flex flex-1 flex-col overflow-hidden text-left"
                    >
                      <span className={clsx('truncate text-[13px]', isActive ? 'font-medium text-foreground' : 'text-foreground/90')}>
                        {session.name}
                      </span>
                      <span className="truncate text-[10px] text-muted-foreground/80">
                        {new Date(session.updatedAt).toLocaleDateString()}
                      </span>
                    </button>
                  )}

                  {!isEditing && (
                    <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        type="button"
                        onClick={() => startEdit(session.id, session.name)}
                        className="rounded p-0.5 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                        title={t('sessionList.rename')}
                      >
                        <Edit2 className="h-3 w-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(session.id)}
                        className="rounded p-0.5 text-muted-foreground hover:bg-surface-2 hover:text-error"
                        title={t('sessionList.delete')}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <Modal
        open={isCreateModalOpen}
        onClose={() => {
          setIsCreateModalOpen(false)
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
                setIsCreateModalOpen(false)
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
    </div>
  )
}
