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
} from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useProjectStore } from '@/stores/projectStore'
import { useTranslation } from '@/i18n'

interface Props {
  collapsed?: boolean
}

export function SidebarSessions({ collapsed = false }: Props) {
  const { t } = useTranslation()

  const sessions = useChatStore((state) => state.sessions)
  const sessionsLoading = useChatStore((state) => state.sessionsLoading)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const currentProjectId = useChatStore((state) => state.currentProjectId)
  const selectSession = useChatStore((state) => state.selectSession)
  const createSession = useChatStore((state) => state.createSession)
  const renameSession = useChatStore((state) => state.renameSession)
  const deleteSession = useChatStore((state) => state.deleteSession)
  const fetchSessions = useChatStore((state) => state.fetchSessions)

  const setCurrentProject = useProjectStore((state) => state.setCurrentProject)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

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
      selectSession(projectSessions[0].id)
    }
  }, [currentProjectId, sessions, currentSessionId, createSession, selectSession, t, sessionsLoading])

  // Keep the chat store's project id in sync with the global project store.
  useEffect(() => {
    setCurrentProject(currentProjectId)
  }, [currentProjectId, setCurrentProject])

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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-t border-border-faint px-3 py-2">
        <span className="px-1 text-[11px] font-semibold tracking-wider text-muted-foreground">
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
                        {session.name || t('sessionList.defaultSession')}
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
    </div>
  )
}
