import { useState } from 'react'
import { clsx } from 'clsx'
import { Plus, Trash2, Edit2, Check, X, MessageSquare } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { Button } from '@/components/ui'

export function SessionList() {
  const sessions = useChatStore((state) => state.sessions)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const setSessionId = useChatStore((state) => state.setSessionId)
  const createSession = useChatStore((state) => state.createSession)
  const renameSession = useChatStore((state) => state.renameSession)
  const deleteSession = useChatStore((state) => state.deleteSession)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

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
    if (confirm('确定要删除此会话吗？')) {
      deleteSession(id)
    }
  }

  return (
    <div className="flex h-full flex-col border-r border-border bg-card">
      <div className="flex items-center justify-between border-b border-border p-3">
        <h2 className="text-sm font-semibold text-foreground">会话</h2>
        <Button size="sm" onClick={() => createSession()}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          新建
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            暂无会话
          </div>
        ) : (
          <div className="divide-y divide-border">
            {sessions.map((session) => {
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
                        title="重命名"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(session.id)}
                        title="删除"
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
    </div>
  )
}
