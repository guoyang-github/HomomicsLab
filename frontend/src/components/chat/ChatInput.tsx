import { useState, useRef, useCallback, useEffect } from 'react'
import { clsx } from 'clsx'
import { Send, Paperclip, Loader2, X, FileText, Command, Map } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { useChatStore } from '@/stores/chatStore'
import { useTaskStore } from '@/stores/taskStore'
import { usePlanStore } from '@/stores/planStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useTranslation } from '@/i18n'
import { chatApi, fileApi } from '@/services/api'
import { Button } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import type { ChatMessage, PlanRequestContent } from '@/types/chat'
import type { SendMessageResponse } from '@/types/api'
import type { TaskProgress } from '@/types/tasks'

function generateSessionName(message: string): string {
  const cleaned = message.replace(/@file:[^\s]+/g, '').replace(/@skill:[^\s]+/g, '').trim()
  return cleaned.slice(0, 40) || 'New Session'
}

interface PendingFile {
  file: File
  id: string
  uploading: boolean
  uploaded: boolean
  error?: string
}

export function ChatInput({ onOpenCommandPalette }: { onOpenCommandPalette?: () => void }) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [planMode, setPlanMode] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const consumedDraftRef = useRef<string | null>(null)

  const {
    addMessage,
    currentSessionId,
    currentProjectId,
    setIsTyping,
    createSession,
    draftInput,
    setDraftInput,
  } = useChatStore()
  const { setTaskTree, setProgress } = useTaskStore()
  const { loadPlan, discardDraft } = usePlanStore()
  const { setJobId, reset: resetExecution } = useExecutionStore()

  useEffect(() => {
    if (!draftInput || consumedDraftRef.current === draftInput) return
    consumedDraftRef.current = draftInput
    setInput((prev) => {
      const separator = prev && !prev.endsWith(' ') ? ' ' : ''
      return prev + separator + draftInput
    })
    setDraftInput('')
    textareaRef.current?.focus()
  }, [draftInput, setDraftInput])

  const processSendResponse = (response: { data: SendMessageResponse }) => {
    const tasks = response.data.task_tree?.tasks || []
    setTaskTree(tasks)
    setProgress(_extractProgress(tasks))
    const lastMsg = response.data.messages[response.data.messages.length - 1]

    // Prefer the backend's top-level response, but fall back to the last stored
    // message content if the response field is empty/whitespace.
    const responseText =
      response.data.response?.trim() ||
      (typeof lastMsg?.content === 'string' ? lastMsg.content : '')

    let agentMessage: ChatMessage
    if (response.data.status === 'awaiting_plan_approval' && response.data.plan) {
      const planContent: PlanRequestContent = {
        plan_id: response.data.plan_id || response.data.plan.plan_id,
        response_text: responseText,
        plan: response.data.plan,
      }
      loadPlan(planContent)
      agentMessage = {
        id: `msg_${Date.now()}_agent`,
        type: 'plan_request',
        content: planContent as unknown as Record<string, unknown>,
        sender: 'agent',
        timestamp: new Date().toISOString(),
      }
    } else if (lastMsg?.type === 'execution_plan') {
      agentMessage = {
        id: `msg_${Date.now()}_agent`,
        type: 'execution_plan',
        content: lastMsg.content,
        sender: 'agent',
        timestamp: new Date().toISOString(),
      }
    } else if (response.data.status === 'completed' && tasks.length === 0) {
      agentMessage = {
        id: `msg_${Date.now()}_agent`,
        type: 'text',
        content: responseText,
        sender: 'agent',
        timestamp: new Date().toISOString(),
      }
    } else {
      const progress = _extractProgress(tasks)
      agentMessage = {
        id: `msg_${Date.now()}_agent`,
        type: 'todo_list',
        content: {
          text: responseText,
          tasks: tasks,
          progress,
          job_id: response.data.job_id || undefined,
        },
        sender: 'agent',
        timestamp: new Date().toISOString(),
      }
    }
    addMessage(agentMessage)

    // Start monitoring any queued job.
    if (response.data.job_id) {
      resetExecution()
      setJobId(response.data.job_id)
      setTaskTree(tasks)
      const progress = _extractProgress(tasks)
      setProgress(progress)
    }
  }

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = createSession()
    }

    const currentSession = useChatStore.getState().getCurrentSession()
    if (currentSession) {
      const isGenericName =
        currentSession.name === 'Default Session' || currentSession.name.startsWith('Session ')
      if (isGenericName) {
        useChatStore.getState().renameSession(currentSession.id, generateSessionName(trimmed))
      }
    }

    discardDraft()

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      type: 'text',
      content: trimmed,
      sender: 'user',
      timestamp: new Date().toISOString(),
    }
    addMessage(userMessage)
    setInput('')
    consumedDraftRef.current = null
    setIsLoading(true)
    setIsTyping(true)

    // Natural-language shortcuts.
    const isRegenerateCmd = /^(重新输出|regenerate|retry|再试一次|重新生成)$/i.test(trimmed)
    const isHelpShortcut = trimmed === '?'

    try {
      if (isRegenerateCmd) {
        const response = await chatApi.regenerate({
          project_id: currentProjectId,
          session_id: sessionId,
          message: '',
          plan_mode: planMode,
        })
        processSendResponse(response)
        return
      }

      const apiMessage = isHelpShortcut ? 'what can you do?' : trimmed
      const response = await chatApi.sendMessage({
        project_id: currentProjectId,
        session_id: sessionId,
        message: apiMessage,
        plan_mode: planMode,
      })
      processSendResponse(response)
    } catch (error: any) {
      // eslint-disable-next-line no-console
      console.error('Chat send failed:', error)
      const detail = error?.response?.data?.detail || error?.message
      const errorMessage: ChatMessage = {
        id: `msg_${Date.now()}_error`,
        type: 'error',
        content: detail || t('chat.sendFailed'),
        sender: 'system',
        timestamp: new Date().toISOString(),
      }
      addMessage(errorMessage)
      toastError(detail || t('chat.sendFailedShort'))
    } finally {
      setIsLoading(false)
      setIsTyping(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function _extractProgress(tasks: { status: string }[]): TaskProgress {
    const total = tasks.length
    const counts = {
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0,
      awaiting_human: 0,
    }
    tasks.forEach((task) => {
      if (task.status in counts) {
        counts[task.status as keyof typeof counts]++
      }
    })
    return {
      total,
      pending: counts.pending,
      running: counts.running,
      completed: counts.completed,
      failed: counts.failed,
      awaiting_human: counts.awaiting_human,
      percent: total > 0 ? Math.round((counts.completed / total) * 100) : 0,
    }
  }

  const uploadFile = async (file: File, id: string) => {
    setPendingFiles((prev) =>
      prev.map((f) => (f.id === id ? { ...f, uploading: true, error: undefined } : f))
    )
    try {
      await fileApi.uploadFile(file, currentProjectId)
      setPendingFiles((prev) =>
        prev.map((f) => (f.id === id ? { ...f, uploading: false, uploaded: true } : f))
      )
      toastSuccess(t('chat.uploaded', { filename: file.name }))
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      setPendingFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, uploading: false, uploaded: false, error: detail || t('chat.uploadFailed') } : f
        )
      )
      toastError(detail || t('chat.uploadFileFailed', { filename: file.name }))
    }
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map((file) => ({
      file,
      id: `file_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      uploading: false,
      uploaded: false,
    }))
    setPendingFiles((prev) => [...prev, ...newFiles])
    newFiles.forEach((f) => uploadFile(f.file, f.id))
  }, [currentProjectId])

  const { getRootProps, getInputProps, open, isDragActive } = useDropzone({
    onDrop,

    noClick: true,
    accept: {
      'application/octet-stream': ['.h5ad', '.mtx', '.fastq.gz', '.csv', '.tsv', '.gz', '.rds', '.RData', '.rda'],
      'text/csv': ['.csv'],
      'text/tab-separated-values': ['.tsv'],
    },
  })

  const removeFile = (id: string) => {
    setPendingFiles((prev) => prev.filter((f) => f.id !== id))
  }

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'border-t border-border bg-card p-4 transition-colors',
        isDragActive && 'bg-primary/5'
      )}
    >
      <input {...getInputProps()} />

      {isDragActive && (
        <div className="mb-3 rounded-lg border-2 border-dashed border-primary bg-primary/5 p-4 text-center text-sm text-primary">
          {t('chat.dropToUpload')}
        </div>
      )}

      {pendingFiles.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {pendingFiles.map((pending) => (
            <div
              key={pending.id}
              className={clsx(
                'flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs',
                pending.error
                  ? 'border-error/30 bg-error/10 text-error'
                  : pending.uploaded
                  ? 'border-success/30 bg-success/10 text-success'
                  : 'border-border bg-muted'
              )}
            >
              <FileText className="h-3.5 w-3.5" />
              <span className="max-w-[120px] truncate">{pending.file.name}</span>
              {pending.uploading && <Loader2 className="h-3 w-3 animate-spin" />}
              {!pending.uploading && (
                <button onClick={() => removeFile(pending.id)} className="rounded p-0.5 hover:bg-black/5">
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.placeholder')}
            rows={1}
            className={clsx(
              'min-h-[48px] w-full resize-none rounded-xl border border-border bg-muted px-4 py-3 pr-20 text-sm',
              'text-foreground placeholder:text-muted-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2'
            )}
            style={{ maxHeight: '200px' }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement
              target.style.height = 'auto'
              target.style.height = `${Math.min(target.scrollHeight, 200)}px`
            }}
          />
          <div className="absolute bottom-2 right-2 flex items-center gap-1">
            <Button
              variant={planMode ? 'secondary' : 'ghost'}
              size="icon"
              onClick={() => setPlanMode((prev) => !prev)}
              title={planMode ? t('chat.planModeActive') : t('chat.planMode')}
            >
              <Map className={clsx('h-4 w-4', planMode && 'text-primary')} />
            </Button>
            <Button variant="ghost" size="icon" onClick={open} title={t('chat.uploadFile')}>
              <Paperclip className="h-4 w-4" />
            </Button>
            {onOpenCommandPalette && (
              <Button variant="ghost" size="icon" onClick={onOpenCommandPalette} title={t('chat.commandPalette')}>
                <Command className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        <Button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="h-12 w-12 shrink-0 rounded-xl p-0"
        >
          {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
        </Button>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>{t('chat.sendHint')}</span>
        <span>{t('chat.formatHint')}</span>
      </div>
    </div>
  )
}
