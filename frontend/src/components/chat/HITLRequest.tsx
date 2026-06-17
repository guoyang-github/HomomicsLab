import { useState } from 'react'
import { clsx } from 'clsx'
import { AlertTriangle, AlertCircle, ShieldAlert, CircleDollarSign, Search, Check } from 'lucide-react'
import { chatApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { useTranslation } from '@/i18n'
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

export function HITLRequest({ checkpoint, taskId }: Props) {
  const { t } = useTranslation()
  const triggerConfig: Record<string, { icon: React.ElementType; label: string; variant: any; color: string }> = {
    reviewer_reject: { icon: Search, label: t('hitl.reviewReject'), variant: 'warning', color: 'text-warning' },
    worker_failure: { icon: AlertTriangle, label: t('hitl.workerFailure'), variant: 'error', color: 'text-error' },
    phase_gate_fail: { icon: AlertCircle, label: t('hitl.phaseGateFail'), variant: 'warning', color: 'text-warning' },
    high_cost: { icon: CircleDollarSign, label: t('hitl.highCost'), variant: 'warning', color: 'text-warning' },
    high_risk: { icon: ShieldAlert, label: t('hitl.highRisk'), variant: 'error', color: 'text-error' },
  }

  const recommendedAction = (checkpoint.metadata?.recommended_action as string) || checkpoint.default_option?.id
  const riskLevel = (checkpoint.metadata?.risk_level as string) || 'medium'

  const [selectedOption, setSelectedOption] = useState(recommendedAction || checkpoint.default_option?.id || '')
  const [parameters, setParameters] = useState('{}')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { currentSessionId, addMessage } = useChatStore()

  const config = triggerConfig[checkpoint.trigger_reason] || {
    icon: AlertCircle,
    label: t('hitl.confirmationNeeded'),
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
          toastError(t('common.invalidJson'))
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

      const confirmedLabel = checkpoint.options.find((o) => o.id === selectedOption)?.label || selectedOption
      toastSuccess(t('hitl.confirmed'))
      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: t('hitl.confirmedAction', { label: confirmedLabel }),
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } catch (error: any) {
      toastError(error?.response?.data?.detail || t('common.submitFailed'))
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
          <Badge variant={config.variant} size="sm">{t('hitl.riskLabel', { level: riskLevel })}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">{t('hitl.reasonLabel')}</span>
            {checkpoint.trigger_reason}
          </p>
          <p className="text-muted-foreground">{checkpoint.context_summary}</p>
        </div>

        {recommendedAction && (
          <p className="text-xs font-medium text-foreground">
            {t('hitl.recommendedAction')} {checkpoint.options.find((o) => o.id === recommendedAction)?.label}
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
          <label className="text-sm font-medium">{t('debate.parametersJson')}</label>
          <Textarea
            value={parameters}
            onChange={(e) => setParameters(e.target.value)}
            rows={2}
            placeholder='{"n_neighbors": 15}'
          />
        </div>

        <Button onClick={handleSubmit} loading={isSubmitting} disabled={!selectedOption}>
          <Check className="mr-1.5 h-4 w-4" />
          {t('common.confirm')}
        </Button>
      </CardContent>
    </Card>
  )
}
