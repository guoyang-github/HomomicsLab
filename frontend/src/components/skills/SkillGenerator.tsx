import { useState } from 'react'
import { Wand2, Sparkles, FileCode2, Check } from 'lucide-react'
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

export function SkillGenerator() {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('custom')
  const [toolType, setToolType] = useState('python')
  const [primaryTool, setPrimaryTool] = useState('')
  const [supportedTools, setSupportedTools] = useState('')
  const [keywords, setKeywords] = useState('')
  const [dependencies, setDependencies] = useState('')
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
      setError('名称和描述为必填项')
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
          inputs: [{ name: 'input_file', description: 'Input data file' }],
          outputs: ['output_file'],
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
      toastSuccess('Skill 生成成功')
    } catch (err) {
      setError('生成 Skill 失败')
      toastError('生成 Skill 失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-card px-4 py-4">
        <div className="flex items-center gap-2">
          <Wand2 className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">Skill 生成器</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">根据需求描述生成新的 Skill</p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-1/2 overflow-y-auto border-r border-border p-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">名称 *</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：Seurat 聚类" />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">描述 *</label>
                <Button type="button" variant="ghost" size="sm" onClick={handleSuggest}>
                  <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                  自动建议
                </Button>
              </div>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="这个 Skill 做什么？"
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">分类</label>
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
                <label className="text-sm font-medium">工具类型</label>
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
              <label className="text-sm font-medium">主要工具</label>
              <Input value={primaryTool} onChange={(e) => setPrimaryTool(e.target.value)} placeholder="例如：scanpy, Seurat" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">支持工具（逗号分隔）</label>
              <Input value={supportedTools} onChange={(e) => setSupportedTools(e.target.value)} placeholder="scanpy, anndata, numpy" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">关键词（逗号分隔）</label>
              <Input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="qc, filtering, single-cell" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">依赖（逗号分隔）</label>
              <Input value={dependencies} onChange={(e) => setDependencies(e.target.value)} placeholder="scanpy, anndata, matplotlib" />
            </div>

            {error && <p className="text-sm text-error">{error}</p>}

            <Button onClick={handleGenerate} loading={loading} className="w-full">
              {loading ? '生成中...' : '生成 Skill'}
            </Button>
          </div>
        </div>

        <div className="w-1/2 overflow-hidden bg-muted/30">
          {generatedFiles.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <FileCode2 className="mx-auto mb-3 h-12 w-12 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">填写表单并点击生成</p>
              </div>
            </div>
          ) : (
            <div className="flex h-full flex-col">
              <div className="border-b border-border bg-card px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Check className="h-4 w-4 text-success" />
                  已生成：{skillId}
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
