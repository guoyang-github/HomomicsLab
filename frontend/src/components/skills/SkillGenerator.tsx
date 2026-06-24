import { useState } from 'react'
import { Wand2, Sparkles, FileCode2, Check, Plus, Trash2 } from 'lucide-react'
import { useTranslation } from '@/i18n'
import {
  Button,
  Input,
  Textarea,
  Select,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'

interface GeneratedFile {
  path: string
  content: string
}

interface SkillInput {
  id: string
  name: string
  description: string
  required: boolean
  default: string
}

export function SkillGenerator() {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('custom')
  const [toolType, setToolType] = useState('python')
  const [primaryTool, setPrimaryTool] = useState('')
  const [supportedTools, setSupportedTools] = useState('')
  const [keywords, setKeywords] = useState('')
  const [dependencies, setDependencies] = useState('')
  const [inputs, setInputs] = useState<SkillInput[]>([
    { id: '1', name: 'input_file', description: 'Input data file', required: true, default: '' },
  ])
  const [outputs, setOutputs] = useState<{ id: string; name: string }[]>([
    { id: '1', name: 'output_file' },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([])
  const [skillId, setSkillId] = useState('')

  const handleSuggest = async () => {
    if (!description.trim()) return
    try {
      const response = await fetch('/api/skill-generator/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description }),
      })
      if (response.ok) {
        const data = await response.json()
        setToolType(data.tool_type)
        setCategory(data.category)
        setKeywords(data.keywords)
      }
    } catch (err) {
      console.error('Suggest failed:', err)
    }
  }

  const handleGenerate = async () => {
    if (!name.trim() || !description.trim()) {
      setError(t('skills.generator.requiredFields'))
      return
    }

    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/skill-generator/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          category,
          tool_type: toolType,
          primary_tool: primaryTool,
          supported_tools: supportedTools.split(',').map((s) => s.trim()).filter(Boolean),
          keywords: keywords.split(',').map((s) => s.trim()).filter(Boolean),
          dependencies: dependencies.split(',').map((s) => s.trim()).filter(Boolean),
          inputs: inputs.map((inp) => ({
            name: inp.name,
            description: inp.description,
            required: inp.required,
            default: inp.default || undefined,
          })),
          outputs: outputs.map((out) => out.name),
        }),
      })

      if (!response.ok) throw new Error('Generation failed')

      const data = await response.json()
      setSkillId(data.skill_id)
      const files = Object.entries(data.files).map(([path, content]) => ({
        path,
        content: content as string,
      }))
      setGeneratedFiles(files)
      toastSuccess(t('skills.generator.success'))
    } catch (err) {
      setError(t('skills.generator.failed'))
      toastError(t('skills.generator.failed'))
    } finally {
      setLoading(false)
    }
  }

  const addInput = () => {
    setInputs((prev) => [
      ...prev,
      { id: crypto.randomUUID(), name: '', description: '', required: false, default: '' },
    ])
  }

  const updateInput = (id: string, field: keyof SkillInput, value: string | boolean) => {
    setInputs((prev) => prev.map((inp) => (inp.id === id ? { ...inp, [field]: value } : inp)))
  }

  const removeInput = (id: string) => {
    setInputs((prev) => prev.filter((inp) => inp.id !== id))
  }

  const addOutput = () => {
    setOutputs((prev) => [...prev, { id: crypto.randomUUID(), name: '' }])
  }

  const updateOutput = (id: string, value: string) => {
    setOutputs((prev) => prev.map((out) => (out.id === id ? { ...out, name: value } : out)))
  }

  const removeOutput = (id: string) => {
    setOutputs((prev) => prev.filter((out) => out.id !== id))
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-card px-4 py-4">
        <div className="flex items-center gap-2">
          <Wand2 className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">{t('skills.generator.title')}</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{t('skills.generator.subtitle')}</p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-1/2 overflow-y-auto border-r border-border p-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('skills.generator.name')}</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('skills.generator.namePlaceholder')} />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">{t('skills.generator.description')}</label>
                <Button type="button" variant="ghost" size="sm" onClick={handleSuggest}>
                  <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                  {t('skills.generator.suggest')}
                </Button>
              </div>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('skills.generator.descriptionPlaceholder')}
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('skills.generator.category')}</label>
                <Select
                  value={category}
                  options={[
                    { value: 'custom', label: 'Custom' },
                    { value: 'single-cell', label: 'Single Cell' },
                    { value: 'spatial-transcriptomics', label: 'Spatial' },
                    { value: 'genomics', label: 'Genomics' },
                    { value: 'proteomics', label: 'Proteomics' },
                    { value: 'workflows', label: 'Workflows' },
                  ]}
                  onChange={(e) => setCategory(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('skills.generator.toolType')}</label>
                <Select
                  value={toolType}
                  options={[
                    { value: 'python', label: 'Python' },
                    { value: 'r', label: 'R' },
                    { value: 'mixed', label: 'Mixed' },
                  ]}
                  onChange={(e) => setToolType(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">{t('skills.generator.primaryTool')}</label>
              <Input value={primaryTool} onChange={(e) => setPrimaryTool(e.target.value)} placeholder={t('skills.generator.primaryToolPlaceholder')} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('skills.generator.supportedTools')}</label>
              <Input value={supportedTools} onChange={(e) => setSupportedTools(e.target.value)} placeholder="scanpy, anndata, numpy" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('skills.generator.keywords')}</label>
              <Input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="qc, filtering, single-cell" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('skills.generator.dependencies')}</label>
              <Input value={dependencies} onChange={(e) => setDependencies(e.target.value)} placeholder="scanpy, anndata, matplotlib" />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">{t('skills.generator.inputs')}</label>
                <Button type="button" variant="ghost" size="sm" onClick={addInput}>
                  <Plus className="mr-1 h-3.5 w-3.5" />
                  {t('skills.generator.addInput')}
                </Button>
              </div>
              <div className="space-y-2">
                {inputs.map((inp) => (
                  <div key={inp.id} className="rounded-lg border border-border bg-card p-2">
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        value={inp.name}
                        onChange={(e) => updateInput(inp.id, 'name', e.target.value)}
                        placeholder={t('skills.generator.inputName')}
                      />
                      <Input
                        value={inp.description}
                        onChange={(e) => updateInput(inp.id, 'description', e.target.value)}
                        placeholder={t('skills.generator.inputDescription')}
                      />
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <Input
                        value={inp.default}
                        onChange={(e) => updateInput(inp.id, 'default', e.target.value)}
                        placeholder="Default value (optional)"
                        className="flex-1"
                      />
                      <label className="flex items-center gap-1.5 whitespace-nowrap text-xs text-muted-foreground">
                        <Input
                          type="checkbox"
                          checked={inp.required}
                          onChange={(e) => updateInput(inp.id, 'required', e.target.checked)}
                          className="h-4 w-4"
                        />
                        {t('skills.generator.inputRequired')}
                      </label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeInput(inp.id)}
                        title={t('skills.generator.removeInput')}
                      >
                        <Trash2 className="h-4 w-4 text-error" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">{t('skills.generator.outputs')}</label>
                <Button type="button" variant="ghost" size="sm" onClick={addOutput}>
                  <Plus className="mr-1 h-3.5 w-3.5" />
                  {t('skills.generator.addOutput')}
                </Button>
              </div>
              <div className="space-y-2">
                {outputs.map((out) => (
                  <div key={out.id} className="flex items-center gap-2">
                    <Input
                      value={out.name}
                      onChange={(e) => updateOutput(out.id, e.target.value)}
                      placeholder={t('skills.generator.outputName')}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeOutput(out.id)}
                      title={t('skills.generator.removeOutput')}
                    >
                      <Trash2 className="h-4 w-4 text-error" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {error && <p className="text-sm text-error">{error}</p>}

            <Button onClick={handleGenerate} loading={loading} className="w-full">
              {loading ? t('skills.generator.generating') : t('skills.generator.generate')}
            </Button>
          </div>
        </div>

        <div className="w-1/2 overflow-hidden bg-muted/30">
          {generatedFiles.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <FileCode2 className="mx-auto mb-3 h-12 w-12 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">{t('skills.generator.empty')}</p>
              </div>
            </div>
          ) : (
            <div className="flex h-full flex-col">
              <div className="border-b border-border bg-card px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Check className="h-4 w-4 text-success" />
                  {t('skills.generator.generated', { skillId })}
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                <div className="space-y-3">
                  {generatedFiles.map((file) => (
                    <Card key={file.path}>
                      <CardHeader className="border-b border-border bg-muted/50 py-2">
                        <CardTitle className="text-xs font-medium text-muted-foreground">{file.path}</CardTitle>
                      </CardHeader>
                      <CardContent className="p-0">
                        <pre className="max-h-64 overflow-auto p-4 text-xs leading-relaxed">
                          <code>{file.content}</code>
                        </pre>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
