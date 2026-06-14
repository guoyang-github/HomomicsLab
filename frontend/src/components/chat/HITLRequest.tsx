import { useState } from 'react'
import { chatApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'

interface Option {
  id: string
  label: string
  description?: string
}

interface Props {
  checkpoint: {
    id: string
    trigger_reason: string
    context_summary: string
    options: Option[]
    default_option?: Option
    metadata?: Record<string, unknown>
  }
  taskId: string
}

const triggerStyles: Record<string, { icon: string; border: string; bg: string; text: string }> = {
  reviewer_reject: {
    icon: '🔍',
    border: 'border-orange-300',
    bg: 'bg-orange-50',
    text: 'text-orange-900',
  },
  worker_failure: {
    icon: '⚠️',
    border: 'border-red-300',
    bg: 'bg-red-50',
    text: 'text-red-900',
  },
  phase_gate_fail: {
    icon: '🚧',
    border: 'border-yellow-300',
    bg: 'bg-yellow-50',
    text: 'text-yellow-900',
  },
  high_cost: {
    icon: '💰',
    border: 'border-purple-300',
    bg: 'bg-purple-50',
    text: 'text-purple-900',
  },
  high_risk: {
    icon: '🛡️',
    border: 'border-red-300',
    bg: 'bg-red-50',
    text: 'text-red-900',
  },
}

export function HITLRequest({ checkpoint, taskId }: Props) {
  const recommendedAction = (checkpoint.metadata?.recommended_action as string) || checkpoint.default_option?.id
  const riskLevel = (checkpoint.metadata?.risk_level as string) || 'medium'

  const [selectedOption, setSelectedOption] = useState(recommendedAction || checkpoint.default_option?.id || '')
  const [parameters, setParameters] = useState('{}')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { currentSessionId, addMessage } = useChatStore()

  const style = triggerStyles[checkpoint.trigger_reason] || {
    icon: '⚠️',
    border: 'border-warning',
    bg: 'bg-yellow-50',
    text: 'text-yellow-900',
  }

  const handleSubmit = async () => {
    if (!selectedOption) return

    setIsSubmitting(true)
    try {
      let parsedParams = {}
      if (parameters.trim()) {
        try {
          parsedParams = JSON.parse(parameters)
        } catch {
          alert('参数 JSON 格式无效，请检查输入')
          setIsSubmitting(false)
          return
        }
      }

      await chatApi.respondToHITL({
        session_id: currentSessionId,
        task_id: taskId,
        choice: selectedOption,
        parameters: parsedParams,
      })

      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: `已确认：${checkpoint.options.find((o) => o.id === selectedOption)?.label}`,
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-3`}>
      <p className={`mb-2 text-sm font-medium ${style.text}`}>
        {style.icon} 需要您确认
        {riskLevel && (
          <span className="ml-2 rounded px-1.5 py-0.5 text-xs capitalize text-white bg-black/20">
            风险：{riskLevel}
          </span>
        )}
      </p>
      <p className={`mb-1 text-sm ${style.text} opacity-90`}>
        原因：{checkpoint.trigger_reason}
      </p>
      <p className={`mb-3 text-sm ${style.text} opacity-80`}>{checkpoint.context_summary}</p>

      {recommendedAction && (
        <p className="mb-2 text-xs font-medium text-slate-600">
          推荐操作：{checkpoint.options.find((o) => o.id === recommendedAction)?.label}
        </p>
      )}

      <div className="mb-3 space-y-2">
        {checkpoint.options.map((option) => (
          <label
            key={option.id}
            className={`flex cursor-pointer items-start gap-2 rounded p-2 text-sm ${
              selectedOption === option.id ? 'bg-white/60' : 'hover:bg-white/40'
            }`}
          >
            <input
              type="radio"
              name={`hitl-${checkpoint.id}`}
              value={option.id}
              checked={selectedOption === option.id}
              onChange={() => setSelectedOption(option.id)}
              className="mt-1"
            />
            <div>
              <div className="font-medium">{option.label}</div>
              {option.description && (
                <div className="text-xs opacity-75">{option.description}</div>
              )}
            </div>
          </label>
        ))}
      </div>

      <div className="mb-3">
        <label className={`mb-1 block text-xs font-medium ${style.text}`}>
          参数 (JSON)
        </label>
        <textarea
          value={parameters}
          onChange={(e) => setParameters(e.target.value)}
          rows={2}
          className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
          placeholder='{"n_neighbors": 15}'
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={!selectedOption || isSubmitting}
        className="rounded bg-warning px-3 py-1.5 text-sm font-medium text-white hover:bg-yellow-600 disabled:opacity-50"
      >
        {isSubmitting ? '提交中...' : '确认'}
      </button>
    </div>
  )
}
