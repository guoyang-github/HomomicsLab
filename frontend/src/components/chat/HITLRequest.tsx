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
  }
  taskId: string
}

export function HITLRequest({ checkpoint, taskId }: Props) {
  const [selectedOption, setSelectedOption] = useState(checkpoint.default_option?.id || '')
  const [parameters, setParameters] = useState('{}')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { currentSessionId, addMessage } = useChatStore()

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
        content: `已确认：${checkpoint.options.find(o => o.id === selectedOption)?.label}`,
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="rounded-lg border border-warning bg-yellow-50 p-3">
      <p className="mb-2 text-sm font-medium text-yellow-900">
        ⚠️ 需要您确认
      </p>
      <p className="mb-3 text-sm text-yellow-800">{checkpoint.context_summary}</p>

      <div className="mb-3 space-y-2">
        {checkpoint.options.map((option) => (
          <label
            key={option.id}
            className={`flex cursor-pointer items-start gap-2 rounded p-2 text-sm ${
              selectedOption === option.id ? 'bg-yellow-100' : 'hover:bg-yellow-100'
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
                <div className="text-xs text-yellow-700">{option.description}</div>
              )}
            </div>
          </label>
        ))}
      </div>

      <div className="mb-3">
        <label className="mb-1 block text-xs font-medium text-yellow-800">
          参数 (JSON)
        </label>
        <textarea
          value={parameters}
          onChange={(e) => setParameters(e.target.value)}
          rows={2}
          className="w-full rounded border border-yellow-300 px-2 py-1 text-xs"
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
