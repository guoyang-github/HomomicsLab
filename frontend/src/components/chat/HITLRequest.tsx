import { useState } from 'react'
import { clsx } from 'clsx'
import { AlertTriangle, AlertCircle, ShieldAlert, CircleDollarSign, Search, Check } from 'lucide-react'
import { chatApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { Button, Card, CardHeader, CardTitle, CardContent, Badge, Textarea } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'

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

const triggerConfig: Record<string, { icon: React.ElementType; label: string; variant: any; color: string }> = {
  reviewer_reject: { icon: Search, label: '审核拒绝', variant: 'warning', color: 'text-warning' },
  worker_failure: { icon: AlertTriangle, label: '执行失败', variant: 'error', color: 'text-error' },
  phase_gate_fail: { icon: AlertCircle, label: '阶段检查未通过', variant: 'warning', color: 'text-warning' },
  high_cost: { icon: CircleDollarSign, label: '高成本', variant: 'warning', color: 'text-warning' },
  high_risk: { icon: ShieldAlert, label: '高风险', variant: 'error', color: 'text-error' },
}

export function HITLRequest({ checkpoint, taskId }: Props) {
  const recommendedAction = (checkpoint.metadata?.recommended_action as string) || checkpoint.default_option?.id
  const riskLevel = (checkpoint.metadata?.risk_level as string) || 'medium'

  const [selectedOption, setSelectedOption] = useState(recommendedAction || checkpoint.default_option?.id || '')
  const [parameters, setParameters] = useState('{}')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { currentSessionId, addMessage } = useChatStore()

  const config = triggerConfig[checkpoint.trigger_reason] || {
    icon: AlertCircle,
    label: '需要确认',
    variant: 'warning',
    color: 'text-warning',
  }
  const Icon = config.icon

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

      await chatApi.respondToHITL({
        session_id: currentSessionId,
        task_id: taskId,
        choice: selectedOption,
        parameters: parsedParams,
      })

      toastSuccess('已确认操作')
      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: `已确认：${checkpoint.options.find((o) => o.id === selectedOption)?.label}`,
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } catch (error: any) {
      toastError(error?.response?.data?.detail || '提交失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="border-warning/30 bg-warning/5">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Icon className={clsx('h-5 w-5', config.color)} />
          <CardTitle className="text-base">{config.label}</CardTitle>
          <Badge variant={config.variant} size="sm">风险：{riskLevel}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">原因：</span>
            {checkpoint.trigger_reason}
          </p>
          <p className="text-muted-foreground">{checkpoint.context_summary}</p>
        </div>

        {recommendedAction && (
          <p className="text-xs font-medium text-foreground">
            推荐操作：{checkpoint.options.find((o) => o.id === recommendedAction)?.label}
          </p>
        )}

        <div className="space-y-2">
          {checkpoint.options.map((option) => (
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
                name={`hitl-${checkpoint.id}`}
                value={option.id}
                checked={selectedOption === option.id}
                onChange={() => setSelectedOption(option.id)}
                className="mt-1 h-4 w-4 accent-primary"
              />
              <div>
                <div className="font-medium">{option.label}</div>
                {option.description && (
                  <div className="text-xs text-muted-foreground">{option.description}</div>
                )}
              </div>
            </label>
          ))}
        </div>

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
          确认
        </Button>
      </CardContent>
    </Card>
  )
}
