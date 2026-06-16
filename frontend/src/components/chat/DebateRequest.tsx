import { useState } from 'react'
import { clsx } from 'clsx'
import { MessagesSquare, Check, Star } from 'lucide-react'
import { chatApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { Button, Card, CardHeader, CardTitle, CardContent, Badge, Textarea } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
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
          toastError('参数 JSON 格式无效')
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
      toastSuccess(`已选择：${chosen?.label || selectedOption}`)
      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: `已选择：${chosen?.label || selectedOption}`,
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } catch (error: any) {
      toastError(error?.response?.data?.detail || '提交失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderOption = (option: DebateOption) => {
    const isRecommended = option.id === recommendation?.id
    return (
      <label
        key={option.id}
        className={clsx(
          'flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm transition-colors',
          selectedOption === option.id
            ? 'border-primary bg-primary/5'
            : 'border-border bg-card hover:bg-muted/50'
        )}
      >
        <input
          type="radio"
          name={`debate-${content.debate_id}`}
          value={option.id}
          checked={selectedOption === option.id}
          onChange={() => setSelectedOption(option.id)}
          className="mt-1 h-4 w-4 accent-primary"
        />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{option.label}</span>
            {isRecommended && (
              <Badge variant="success" size="sm">
                <Star className="mr-1 h-3 w-3" />
                推荐
              </Badge>
            )}
          </div>
          {option.description && (
            <div className="mt-0.5 text-xs text-muted-foreground">{option.description}</div>
          )}
          {option.score !== undefined && (
            <div className="mt-1 text-xs text-muted-foreground">得分：{option.score.toFixed(2)}</div>
          )}
        </div>
      </label>
    )
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <MessagesSquare className="h-5 w-5 text-primary" />
          <CardTitle className="text-base">{topic}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {round_summaries && round_summaries.length > 0 && (
          <div className="space-y-1">
            {round_summaries.map((summary, idx) => (
              <p key={idx} className="text-xs text-muted-foreground">
                {summary}
              </p>
            ))}
          </div>
        )}

        <div className="space-y-2">{options.map(renderOption)}</div>

        <div className="space-y-2">
          <label className="text-sm font-medium">参数（JSON）</label>
          <Textarea
            value={parameters}
            onChange={(e) => setParameters(e.target.value)}
            rows={2}
            placeholder='{"n_neighbors": 15}'
          />
        </div>

        <Button onClick={handleSubmit} loading={isSubmitting} disabled={!selectedOption}>
          <Check className="mr-1.5 h-4 w-4" />
          确认选择
        </Button>
      </CardContent>
    </Card>
  )
}
