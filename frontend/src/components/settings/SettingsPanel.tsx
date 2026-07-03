import { useState } from 'react'
import {
  Bot,
  Terminal,
  Search,
  Wallet,
  Settings2,
  Save,
  RotateCcw,
  AlertCircle,
  Globe,
} from 'lucide-react'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Button,
  Input,
  Select,
  Switch,
  Badge,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from '@/components/ui'
import { useAuthStore } from '@/stores/authStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { toastSuccess, toastError } from '@/stores/toastStore'
import { useTranslation } from '@/i18n'

const providerOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'moonshot', label: 'Kimi (Moonshot)' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: 'Qwen' },
  { value: 'local', label: 'Local / Ollama' },
  { value: 'custom', label: 'Custom Endpoint' },
]

const modelOptions: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-5-sonnet-latest', 'claude-3-opus-latest', 'claude-3-haiku-latest'],
  azure: ['gpt-4o', 'gpt-4o-mini'],
  moonshot: ['kimi-k2.6', 'kimi-k2.5', 'moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'],
  deepseek: ['deepseek-chat', 'deepseek-coder', 'deepseek-reasoner'],
  qwen: ['qwen-turbo', 'qwen-plus', 'qwen-max', 'qwen-coder-plus'],
  local: ['llama3.1', 'qwen2.5', 'mistral', 'deepseek-coder'],
  custom: ['custom-model'],
}

const sandboxOptions = [
  { value: 'subprocess', label: 'Subprocess' },
  { value: 'docker', label: 'Docker' },
  { value: 'local', label: 'Local Environment' },
]

const embeddingOptions = [
  { value: 'text-embedding-3-small', label: 'OpenAI text-embedding-3-small' },
  { value: 'text-embedding-3-large', label: 'OpenAI text-embedding-3-large' },
  { value: 'ollama/nomic-embed-text', label: 'Ollama nomic-embed-text' },
  { value: 'local/BAAI/bge-large-zh-v1.5', label: 'Local BGE Large' },
]

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'zh', label: '中文' },
]

function defaultBaseUrlPlaceholder(provider: string): string {
  switch (provider) {
    case 'local':
      return 'http://localhost:11434'
    case 'moonshot':
      return 'https://api.moonshot.cn/v1'
    case 'deepseek':
      return 'https://api.deepseek.com'
    case 'qwen':
      return 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    case 'azure':
      return 'https://<resource>.openai.azure.com'
    default:
      return 'https://api.openai.com/v1'
  }
}

function apiKeyPlaceholder(provider: string): string {
  return provider === 'local' ? 'Local models usually do not require a key' : 'sk-...'
}

export function SettingsPanel() {
  const { t } = useTranslation()
  const settings = useSettingsStore()
  const auth = useAuthStore()
  const [activeTab, setActiveTab] = useState('model')
  const [hasChanges, setHasChanges] = useState(false)

  const handleChange = () => setHasChanges(true)

  const handleSave = async () => {
    const ok = await settings.saveSettings()
    if (ok) {
      toastSuccess(t('settings.saveSuccess'))
      setHasChanges(false)
    } else {
      toastError(settings.saveError || t('settings.saveFailed'))
    }
  }

  const handleTest = async () => {
    await settings.testConnection()
    if (settings.testResult?.ok) {
      toastSuccess(t('settings.testSuccess'))
    } else {
      toastError(settings.testResult?.message || t('settings.testFailed'))
    }
  }

  const handleReset = () => {
    if (confirm(t('settings.resetConfirm'))) {
      settings.reset()
      toastSuccess(t('settings.resetSuccess'))
      setHasChanges(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{t('settings.title')}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{t('settings.subtitle')}</p>
          </div>
          <div className="flex items-center gap-2">
            {hasChanges && (
              <Badge variant="warning" size="md">
                <AlertCircle className="mr-1 h-3 w-3" />
                {t('settings.unsaved')}
              </Badge>
            )}
            {settings.saveError && (
              <span className="text-sm text-destructive">{settings.saveError}</span>
            )}
            <Button
              variant="outline"
              onClick={handleTest}
              disabled={settings.isTesting || !settings.model.model}
            >
              {settings.isTesting ? t('common.loading') : t('settings.testConnection')}
            </Button>
            <Button variant="outline" onClick={handleReset}>
              <RotateCcw className="mr-1.5 h-4 w-4" />
              {t('common.reset')}
            </Button>
            <Button onClick={handleSave} disabled={settings.isSaving}>
              <Save className="mr-1.5 h-4 w-4" />
              {settings.isSaving ? t('common.loading') : t('common.save')}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="model" value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5 sm:w-auto">
            <TabsTrigger value="model">
              <Bot className="mr-1.5 h-4 w-4" />
              {t('settings.tabs.model')}
            </TabsTrigger>
            <TabsTrigger value="execution">
              <Terminal className="mr-1.5 h-4 w-4" />
              {t('settings.tabs.execution')}
            </TabsTrigger>
            <TabsTrigger value="search">
              <Search className="mr-1.5 h-4 w-4" />
              {t('settings.tabs.search')}
            </TabsTrigger>
            <TabsTrigger value="budget">
              <Wallet className="mr-1.5 h-4 w-4" />
              {t('settings.tabs.budget')}
            </TabsTrigger>
            <TabsTrigger value="general">
              <Settings2 className="mr-1.5 h-4 w-4" />
              {t('settings.tabs.general')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="model" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.model.title')}</CardTitle>
                <CardDescription>{t('settings.model.desc')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.model.provider')}</label>
                  <Select
                    value={settings.model.provider}
                    options={providerOptions}
                    onChange={(e) => {
                      const provider = e.target.value as any
                      settings.updateModel({ provider })
                      settings.updateModel({
                        model: provider === 'custom' ? '' : modelOptions[provider][0],
                      })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.model.model')}</label>
                  {settings.model.provider === 'custom' ? (
                    <Input
                      value={settings.model.model}
                      placeholder="e.g. kimi-for-coding"
                      onChange={(e) => {
                        settings.updateModel({ model: e.target.value })
                        handleChange()
                      }}
                    />
                  ) : (
                    <Select
                      value={settings.model.model}
                      options={modelOptions[settings.model.provider].map((m) => ({ value: m, label: m }))}
                      onChange={(e) => {
                        settings.updateModel({ model: e.target.value })
                        handleChange()
                      }}
                    />
                  )}
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-medium">{t('settings.model.apiKey')}</label>
                    {settings.apiKeySet && !settings.model.apiKey && (
                      <Badge variant="success" size="sm">{t('settings.apiKeySaved')}</Badge>
                    )}
                  </div>
                  <Input
                    type="password"
                    value={settings.model.apiKey}
                    placeholder={apiKeyPlaceholder(settings.model.provider)}
                    onChange={(e) => {
                      settings.updateModel({ apiKey: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <label className="text-sm font-medium">{t('settings.model.baseUrl')}</label>
                  <Input
                    value={settings.model.baseUrl}
                    placeholder={defaultBaseUrlPlaceholder(settings.model.provider)}
                    onChange={(e) => {
                      settings.updateModel({ baseUrl: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t('settings.model.temperature')}: {settings.model.temperature}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={settings.model.temperature}
                    onChange={(e) => {
                      settings.updateModel({ temperature: parseFloat(e.target.value) })
                      handleChange()
                    }}
                    className="w-full accent-primary"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.model.maxTokens')}</label>
                  <Input
                    type="number"
                    value={settings.model.maxTokens}
                    onChange={(e) => {
                      settings.updateModel({ maxTokens: parseInt(e.target.value, 10) || 0 })
                      handleChange()
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="execution" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.execution.title')}</CardTitle>
                <CardDescription>{t('settings.execution.desc')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.execution.sandbox')}</label>
                  <Select
                    value={settings.execution.sandboxBackend}
                    options={sandboxOptions}
                    onChange={(e) => {
                      settings.updateExecution({ sandboxBackend: e.target.value as any })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.execution.timeout')}</label>
                  <Input
                    type="number"
                    value={settings.execution.timeoutSeconds}
                    onChange={(e) => {
                      settings.updateExecution({ timeoutSeconds: parseInt(e.target.value, 10) || 0 })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.execution.workDir')}</label>
                  <Input
                    value={settings.execution.workDir}
                    onChange={(e) => {
                      settings.updateExecution({ workDir: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.execution.dataDir')}</label>
                  <Input
                    value={settings.execution.dataDir}
                    onChange={(e) => {
                      settings.updateExecution({ dataDir: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <label className="text-sm font-medium">{t('settings.execution.memory')}</label>
                  <Input
                    type="number"
                    value={settings.execution.memoryLimitMb}
                    onChange={(e) => {
                      settings.updateExecution({ memoryLimitMb: parseInt(e.target.value, 10) || 0 })
                      handleChange()
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="search" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.search.title')}</CardTitle>
                <CardDescription>{t('settings.search.desc')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <label className="text-sm font-medium">{t('settings.search.embedding')}</label>
                  <Select
                    value={settings.search.embeddingModel}
                    options={embeddingOptions}
                    onChange={(e) => {
                      settings.updateSearch({ embeddingModel: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t('settings.search.topK')}: {settings.search.topK}
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    step="1"
                    value={settings.search.topK}
                    onChange={(e) => {
                      settings.updateSearch({ topK: parseInt(e.target.value, 10) })
                      handleChange()
                    }}
                    className="w-full accent-primary"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t('settings.search.threshold')}: {settings.search.similarityThreshold}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={settings.search.similarityThreshold}
                    onChange={(e) => {
                      settings.updateSearch({ similarityThreshold: parseFloat(e.target.value) })
                      handleChange()
                    }}
                    className="w-full accent-primary"
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="budget" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.budget.title')}</CardTitle>
                <CardDescription>{t('settings.budget.desc')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.budget.perRequest')}</label>
                  <Input
                    type="number"
                    step="0.1"
                    value={settings.budget.perRequestBudget}
                    onChange={(e) => {
                      settings.updateBudget({ perRequestBudget: parseFloat(e.target.value) || 0 })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.budget.monthly')}</label>
                  <Input
                    type="number"
                    step="0.1"
                    value={settings.budget.monthlyBudget}
                    onChange={(e) => {
                      settings.updateBudget({ monthlyBudget: parseFloat(e.target.value) || 0 })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.budget.tokenThreshold')}</label>
                  <Input
                    type="number"
                    value={settings.budget.approvalThresholdTokens}
                    onChange={(e) => {
                      settings.updateBudget({ approvalThresholdTokens: parseInt(e.target.value, 10) || 0 })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('settings.budget.costThreshold')}</label>
                  <Input
                    type="number"
                    step="0.1"
                    value={settings.budget.approvalThresholdCost}
                    onChange={(e) => {
                      settings.updateBudget({ approvalThresholdCost: parseFloat(e.target.value) || 0 })
                      handleChange()
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="general" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.general.title')}</CardTitle>
                <CardDescription>{t('settings.general.desc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between rounded-lg border border-border p-4">
                  <div className="flex items-center gap-3">
                    <Globe className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">{t('settings.general.language')}</p>
                      <p className="text-sm text-muted-foreground">{t('settings.general.languageDesc')}</p>
                    </div>
                  </div>
                  <Select
                    value={settings.locale}
                    options={languageOptions}
                    onChange={(e) => {
                      settings.setLocale(e.target.value as 'en' | 'zh')
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2 rounded-lg border border-border p-4">
                  <label className="text-sm font-medium">{t('settings.general.authToken')}</label>
                  <p className="text-sm text-muted-foreground">{t('settings.general.authTokenDesc')}</p>
                  <Input
                    type="password"
                    value={auth.token}
                    placeholder={t('settings.general.authTokenHint')}
                    onChange={(e) => {
                      auth.setToken(e.target.value)
                      handleChange()
                    }}
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border p-4">
                  <div>
                    <p className="font-medium">{t('settings.general.autoApprove')}</p>
                    <p className="text-sm text-muted-foreground">{t('settings.general.autoApproveDesc')}</p>
                  </div>
                  <Switch
                    checked={settings.autoApprovePlans}
                    onChange={(e) => {
                      settings.setAutoApprovePlans(e.target.checked)
                      handleChange()
                    }}
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border p-4">
                  <div>
                    <p className="font-medium">{t('settings.general.notifications')}</p>
                    <p className="text-sm text-muted-foreground">{t('settings.general.notificationsDesc')}</p>
                  </div>
                  <Switch
                    checked={settings.enableNotifications}
                    onChange={(e) => {
                      settings.setEnableNotifications(e.target.checked)
                      handleChange()
                    }}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      {t('settings.general.retention')}{' '}
                      {settings.dataRetentionDays === 0 && (
                        <span className="text-muted-foreground">({t('settings.general.retentionForever')})</span>
                      )}
                    </label>
                    <Input
                      type="number"
                      min={0}
                      value={settings.dataRetentionDays}
                      placeholder={t('settings.general.retentionHint')}
                      onChange={(e) => {
                        settings.setDataRetentionDays(parseInt(e.target.value, 10) || 0)
                        handleChange()
                      }}
                    />
                    <p className="text-xs text-muted-foreground">{t('settings.general.retentionHint')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
