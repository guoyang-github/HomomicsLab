import { useState } from 'react'
import { ChevronDown, Wrench } from 'lucide-react'
import { clsx } from 'clsx'
import { useTranslation } from '@/i18n'

interface ToolCallItem {
  tool_name: string
  inputs: Record<string, unknown>
  success: boolean
  output_summary: string
  /** Optional execution duration in milliseconds. */
  duration_ms?: number
  /** Optional explicit status; falls back to `success` when absent. */
  status?: 'running' | 'success' | 'error'
}

export interface ResultPreviewContent {
  tool_calls: ToolCallItem[]
  response_text?: string
}

interface Props {
  content: ResultPreviewContent
}

const OUTPUT_TRUNCATE_AT = 500

type ToolStatus = 'running' | 'success' | 'error'

function statusOf(tc: ToolCallItem): ToolStatus {
  return tc.status ?? (tc.success ? 'success' : 'error')
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function ToolCallCard({ tc }: { tc: ToolCallItem }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const [fullOutput, setFullOutput] = useState(false)
  const status = statusOf(tc)
  const output = tc.output_summary ?? ''
  const isLongOutput = output.length > OUTPUT_TRUNCATE_AT
  const visibleOutput =
    isLongOutput && !fullOutput ? `${output.slice(0, OUTPUT_TRUNCATE_AT)}…` : output

  return (
    <div className="rounded-lg border border-border bg-card/60 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/40"
      >
        <Wrench className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="flex-1 truncate font-medium text-foreground">{tc.tool_name}</span>
        <span
          className={clsx(
            'h-2 w-2 shrink-0 rounded-full',
            status === 'success' && 'bg-success',
            status === 'error' && 'bg-error',
            status === 'running' && 'animate-pulse bg-primary'
          )}
          title={status}
        />
        {status === 'running' && (
          <span className="text-xs text-muted-foreground">{t('toolCall.running')}</span>
        )}
        {tc.duration_ms !== undefined && (
          <span className="shrink-0 font-mono text-xs text-muted-foreground">
            {formatDuration(tc.duration_ms)}
          </span>
        )}
        <ChevronDown
          className={clsx(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-fast',
            expanded && 'rotate-180'
          )}
        />
      </button>

      {!expanded && output && (
        <p className="line-clamp-1 px-3 pb-2 text-xs text-muted-foreground">{output}</p>
      )}

      {expanded && (
        <div className="space-y-2 border-t border-border px-3 py-2 text-xs">
          {tc.inputs && Object.keys(tc.inputs).length > 0 && (
            <div>
              <span className="font-medium text-foreground">{t('common.inputs')}</span>
              <pre className="mt-1 max-h-32 overflow-auto rounded-md bg-muted p-2 font-mono text-2xs leading-relaxed">
                {JSON.stringify(tc.inputs, null, 2)}
              </pre>
            </div>
          )}
          <div>
            <span className="font-medium text-foreground">{t('common.output')}</span>
            <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-2 font-mono text-2xs leading-relaxed">
              {visibleOutput || '—'}
            </pre>
            {isLongOutput && (
              <button
                type="button"
                onClick={() => setFullOutput((v) => !v)}
                className="mt-1 text-2xs text-primary hover:underline"
              >
                {fullOutput ? t('toolCall.collapseOutput') : t('toolCall.showFullOutput')}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function ResultPreview({ content }: Props) {
  return (
    <div className="space-y-2">
      {content.response_text && (
        <p className="text-sm text-foreground/80">{content.response_text}</p>
      )}
      <div className="space-y-2">
        {content.tool_calls.map((tc, idx) => (
          <ToolCallCard key={idx} tc={tc} />
        ))}
      </div>
    </div>
  )
}
