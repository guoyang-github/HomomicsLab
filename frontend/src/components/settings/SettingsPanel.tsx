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
import { useSettingsStore } from '@/stores/settingsStore'
import { toastSuccess } from '@/stores/toastStore'

const providerOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'local', label: 'Local / Ollama' },
  { value: 'custom', label: 'Custom Endpoint' },
]

const modelOptions: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-5-sonnet-latest', 'claude-3-opus-latest', 'claude-3-haiku-latest'],
  azure: ['gpt-4o', 'gpt-4o-mini'],
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

export function SettingsPanel() {
  const settings = useSettingsStore()
  const [activeTab, setActiveTab] = useState('model')
  const [hasChanges, setHasChanges] = useState(false)

  const handleChange = () => setHasChanges(true)

  const handleSave = () => {
    toastSuccess('设置已保存')
    setHasChanges(false)
  }

  const handleReset = () => {
    if (confirm('确定要重置所有设置为默认值吗？')) {
      settings.reset()
      toastSuccess('设置已重置')
      setHasChanges(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">设置</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              配置模型、执行环境、检索与预算参数
            </p>
          </div>
          <div className="flex items-center gap-2">
            {hasChanges && (
              <Badge variant="warning" size="md">
                <AlertCircle className="mr-1 h-3 w-3" />
                未保存
              </Badge>
            )}
            <Button variant="outline" onClick={handleReset}>
              <RotateCcw className="mr-1.5 h-4 w-4" />
              重置
            </Button>
            <Button onClick={handleSave}>
              <Save className="mr-1.5 h-4 w-4" />
              保存
            </Button>
          </div>
        </div>

        <Tabs defaultValue="model" value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5 sm:w-auto">
            <TabsTrigger value="model">
              <Bot className="mr-1.5 h-4 w-4" />
              AI 模型
            </TabsTrigger>
            <TabsTrigger value="execution">
              <Terminal className="mr-1.5 h-4 w-4" />
              执行环境
            </TabsTrigger>
            <TabsTrigger value="search">
              <Search className="mr-1.5 h-4 w-4" />
              语义检索
            </TabsTrigger>
            <TabsTrigger value="budget">
              <Wallet className="mr-1.5 h-4 w-4" />
              预算控制
            </TabsTrigger>
            <TabsTrigger value="general">
              <Settings2 className="mr-1.5 h-4 w-4" />
              通用
            </TabsTrigger>
          </TabsList>

          <TabsContent value="model" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>大语言模型</CardTitle>
                <CardDescription>配置对话与 CodeAct 生成使用的 LLM</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={settings.model.provider}
                    options={providerOptions}
                    onChange={(e) => {
                      settings.updateModel({ provider: e.target.value as any })
                      settings.updateModel({ model: modelOptions[e.target.value][0] })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">模型</label>
                  <Select
                    value={settings.model.model}
                    options={modelOptions[settings.model.provider].map((m) => ({ value: m, label: m }))}
                    onChange={(e) => {
                      settings.updateModel({ model: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <label className="text-sm font-medium">API Key</label>
                  <Input
                    type="password"
                    value={settings.model.apiKey}
                    placeholder={settings.model.provider === 'local' ? 'Local 模型通常无需 Key' : 'sk-...'}
                    onChange={(e) => {
                      settings.updateModel({ apiKey: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <label className="text-sm font-medium">Base URL / Endpoint</label>
                  <Input
                    value={settings.model.baseUrl}
                    placeholder={settings.model.provider === 'local' ? 'http://localhost:11434' : 'https://api.openai.com/v1'}
                    onChange={(e) => {
                      settings.updateModel({ baseUrl: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Temperature: {settings.model.temperature}</label>
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
                  <label className="text-sm font-medium">Max Tokens</label>
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
                <CardTitle>代码执行环境</CardTitle>
                <CardDescription>配置 CodeAct 代码运行环境与资源限制</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">沙箱后端</label>
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
                  <label className="text-sm font-medium">超时时间（秒）</label>
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
                  <label className="text-sm font-medium">工作目录</label>
                  <Input
                    value={settings.execution.workDir}
                    onChange={(e) => {
                      settings.updateExecution({ workDir: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">数据目录</label>
                  <Input
                    value={settings.execution.dataDir}
                    onChange={(e) => {
                      settings.updateExecution({ dataDir: e.target.value })
                      handleChange()
                    }}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <label className="text-sm font-medium">内存限制（MB）</label>
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
                <CardTitle>语义检索</CardTitle>
                <CardDescription>配置 Skill 召回使用的 Embedding 模型</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <label className="text-sm font-medium">Embedding 模型</label>
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
                  <label className="text-sm font-medium">Top-K: {settings.search.topK}</label>
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
                  <label className="text-sm font-medium">相似度阈值: {settings.search.similarityThreshold}</label>
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
                <CardTitle>预算与审批</CardTitle>
                <CardDescription>控制单次与月度成本，设置人工审批阈值</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">单次请求预算（USD）</label>
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
                  <label className="text-sm font-medium">月度预算（USD）</label>
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
                  <label className="text-sm font-medium">Token 审批阈值</label>
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
                  <label className="text-sm font-medium">成本审批阈值（USD）</label>
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
                <CardTitle>通用设置</CardTitle>
                <CardDescription>数据保留、计划审批与通知偏好</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between rounded-lg border border-border p-4">
                  <div>
                    <p className="font-medium">自动批准计划</p>
                    <p className="text-sm text-muted-foreground">跳过计划审批步骤直接执行</p>
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
                    <p className="font-medium">启用通知</p>
                    <p className="text-sm text-muted-foreground">任务完成或需要人工介入时显示提示</p>
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
                    <label className="text-sm font-medium">数据保留天数</label>
                    <Input
                      type="number"
                      value={settings.dataRetentionDays}
                      onChange={(e) => {
                        settings.setDataRetentionDays(parseInt(e.target.value, 10) || 0)
                        handleChange()
                      }}
                    />
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
