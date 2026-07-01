import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Plus, Trash2, Edit2, Check, X, MessageSquare, Loader2 } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useProjectStore } from '@/stores/projectStore'
import { useAnalysisTemplateStore } from '@/stores/analysisTemplateStore'
import { Button, Select, Modal, Input } from '@/components/ui'
import { useTranslation } from '@/i18n'

export function SessionList() {
  const { t } = useTranslation()
  const sessions = useChatStore((state) => state.sessions)
  const sessionsLoading = useChatStore((state) => state.sessionsLoading)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const setSessionId = useChatStore((state) => state.setSessionId)
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
    if (isCreateModalOpen) {
      fetchTemplates()
    }
  }, [isCreateModalOpen, fetchTemplates])

  useEffect(() => {
    fetchSessions(currentProjectId)
  }, [currentProjectId, fetchSessions])

  useEffect(() => {
    if (sessionsLoading) return
    const projectSessions = sessions.filter((s) => s.projectId === currentProjectId)
    if (projectSessions.length === 0) {
      createSession(t('sessionList.defaultSession'), currentProjectId)
      return
    }
    if (!projectSessions.some((s) => s.id === currentSessionId)) {
      setSessionId(projectSessions[0].id)
      clearMessages()
    }
  }, [
    currentProjectId,
    sessions,
    currentSessionId,
    createSession,
    setSessionId,
    clearMessages,
    t,
    sessionsLoading,
  ])

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
    <div className="flex h-full flex-col border-r border-border bg-card">
      <div className="border-b border-border p-3">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">{t('sessionList.title')}</h2>
          <Button size="sm" variant="outline" onClick={() => setIsCreateModalOpen(true)}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t('sessionList.new')}
          </Button>
        </div>
        <Select
          value={currentProjectId}
          onChange={(e) => handleProjectChange(e.target.value)}
          options={projectOptions}
          disabled={loadingProjects}
        />
        {projectError && (
          <div className="mt-2 flex items-center gap-2 rounded-md bg-error/10 px-2 py-1.5">
            <p className="flex-1 text-xs leading-tight text-error">{projectError}</p>
            <Button size="sm" variant="ghost" className="h-auto px-2 py-1 text-xs" onClick={fetchProjects}>
              {t('common.retry')}
            </Button>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-b border-border p-3">
        <h2 className="text-sm font-semibold text-foreground">{t('sessionList.sessions')}</h2>
        <Button size="sm" onClick={() => createSession(undefined, currentProjectId)}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          {t('sessionList.new')}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sessionsLoading ? (
          <div className="flex items-center justify-center p-4 text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            {t('common.loading')}
          </div>
        ) : projectSessions.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            {t('sessionList.noSessions')}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {projectSessions.map((session) => {
              const isActive = session.id === currentSessionId
              const isEditing = editingId === session.id

              return (
                <div
                  key={session.id}
                  className={clsx(
                    'group flex items-center gap-2 p-3 transition-colors',
                    isActive ? 'bg-primary/5' : 'hover:bg-muted/50'
                  )}
                >
                  <MessageSquare className={clsx('h-4 w-4 shrink-0', isActive ? 'text-primary' : 'text-muted-foreground')} />

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
                        className="h-7 flex-1 rounded border border-border bg-card px-2 text-sm"
                      />
                      <Button variant="ghost" size="icon" onClick={saveEdit}>
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => setEditingId(null)}>
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setSessionId(session.id)}
                      className="flex flex-1 flex-col overflow-hidden text-left"
                    >
                      <span className={clsx('truncate text-sm', isActive ? 'font-medium text-primary' : 'text-foreground')}>
                        {session.name}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {new Date(session.updatedAt).toLocaleString()}
                      </span>
                    </button>
                  )}

                  {!isEditing && (
                    <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => startEdit(session.id, session.name)}
                        title={t('sessionList.rename')}
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(session.id)}
                        title={t('sessionList.delete')}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
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
