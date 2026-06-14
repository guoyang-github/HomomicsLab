import { useState } from 'react'
import { chatApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import type { DebateRequestContent, DebateOption } from '@/types/chat'

interface Props {
  content: DebateRequestContent
}

export function DebateRequest({ content }: Props) {
  const { topic, options, recommendation, round_summaries } = content
  const [selectedOption, setSelectedOption] = useState(recommendation?.id || options[0]?.id || '')
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

      await chatApi.respondToDebate({
        session_id: currentSessionId,
        debate_id: content.debate_id,
        choice_id: selectedOption,
        parameters: parsedParams,
      })

      const chosen = options.find((o) => o.id === selectedOption)
      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: `已选择：${chosen?.label || selectedOption}`,
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderOption = (option: DebateOption) => {
    const isRecommended = option.id === recommendation?.id
    return (
      <label
        key={option.id}
        className={`flex cursor-pointer items-start gap-2 rounded border p-2 text-sm transition-colors ${
          selectedOption === option.id
            ? 'border-primary bg-primary/5'
            : 'border-slate-200 hover:bg-slate-50'
        }`}
      >
        <input
          type="radio"
          name={`debate-${content.debate_id}`}
          value={option.id}
          checked={selectedOption === option.id}
          onChange={() => setSelectedOption(option.id)}
          className="mt-1"
        />
        <div className="flex-1">
          <div className="flex items-center gap-2 font-medium">
            {option.label}
            {isRecommended && (
              <span className="rounded bg-success px-1.5 py-0.5 text-xs text-white">推荐</span>
            )}
          </div>
          {option.description && (
            <div className="mt-0.5 text-xs text-slate-500">{option.description}</div>
          )}
          {option.score !== undefined && (
            <div className="mt-0.5 text-xs text-slate-400">得分：{option.score.toFixed(2)}</div>
          )}
        </div>
      </label>
    )
  }

  return (
    <div className="space-y-3 rounded-lg border border-primary/20 bg-primary/5 p-3">
      <div>
        <p className="text-sm font-medium text-slate-800">🗣️ {topic}</p>
        {round_summaries && round_summaries.length > 0 && (
          <div className="mt-1 space-y-0.5">
            {round_summaries.map((summary, idx) => (
              <p key={idx} className="text-xs text-slate-500">
                {summary}
              </p>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2">{options.map(renderOption)}</div>

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">参数 (JSON)</label>
        <textarea
          value={parameters}
          onChange={(e) => setParameters(e.target.value)}
          rows={2}
          className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-xs"
          placeholder='{"n_neighbors": 15}'
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={!selectedOption || isSubmitting}
        className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
      >
        {isSubmitting ? '提交中...' : '确认选择'}
      </button>
    </div>
  )
}
