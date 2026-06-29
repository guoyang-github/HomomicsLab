import { useState } from 'react'
import { CheckCircle2, XCircle, ChevronDown, ChevronUp, Wrench } from 'lucide-react'
import { clsx } from 'clsx'
import { useTranslation } from '@/i18n'

interface ToolCallItem {
  tool_name: string
  inputs: Record<string, unknown>
  success: boolean
  output_summary: string
}

export interface ResultPreviewContent {
  tool_calls: ToolCallItem[]
  response_text?: string
}

interface Props {
  content: ResultPreviewContent
}

export function ResultPreview({ content }: Props) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  const toggle = (idx: number) => {
    setExpanded((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }

  return (
    <div className="space-y-2">
      {content.response_text && (
        <p className="text-sm text-foreground/80">{content.response_text}</p>
      )}
      <div className="space-y-2">
        {content.tool_calls.map((tc, idx) => (
          <div
            key={idx}
            className={clsx(
              'rounded-lg border p-3 text-sm',
              tc.success
                ? 'border-success/20 bg-success/5'
                : 'border-error/20 bg-error/5'
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Wrench className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{tc.tool_name}</span>
                {tc.success ? (
                  <CheckCircle2 className="h-4 w-4 text-success" />
                ) : (
                  <XCircle className="h-4 w-4 text-error" />
                )}
              </div>
              <button
                onClick={() => toggle(idx)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                {expanded[idx] ? (
                  <>
                    <ChevronUp className="h-3.5 w-3.5" /> {t('common.hide')}
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3.5 w-3.5" /> {t('common.details')}
                  </>
                )}
              </button>
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {tc.output_summary}
            </p>
            {expanded[idx] && (
              <div className="mt-2 space-y-2 border-t border-border pt-2 text-xs">
                {Object.keys(tc.inputs).length > 0 && (
                  <div>
                    <span className="font-medium text-foreground">{t('common.inputs')}:</span>
                    <pre className="mt-1 max-h-32 overflow-auto rounded bg-muted p-2">
                      {JSON.stringify(tc.inputs, null, 2)}
                    </pre>
                  </div>
                )}
                <div>
                  <span className="font-medium text-foreground">{t('common.output')}:</span>
                  <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-2">
                    {tc.output_summary}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
