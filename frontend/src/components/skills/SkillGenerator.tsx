import { useState } from 'react'

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
      setError('Name and description are required')
      return
    }

    try {
      setLoading(true)
      setError('')
      const response = await fetch('/api/skill-generator/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          category,
          tool_type: toolType,
          primary_tool: primaryTool,
          supported_tools: supportedTools.split(',').map(s => s.trim()).filter(Boolean),
          keywords: keywords.split(',').map(s => s.trim()).filter(Boolean),
          dependencies: dependencies.split(',').map(s => s.trim()).filter(Boolean),
          inputs: [{ name: 'input_file', description: 'Input data file' }],
          outputs: ['output_file'],
        }),
      })

      if (!response.ok) {
        throw new Error('Generation failed')
      }

      const data = await response.json()
      setSkillId(data.skill_id)
      const files = Object.entries(data.files).map(([path, content]) => ({
        path,
        content: content as string,
      }))
      setGeneratedFiles(files)
    } catch (err) {
      setError('Failed to generate skill')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-800">Skill Generator</h2>
        <p className="text-xs text-slate-500">Generate new skills from requirements</p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Form */}
        <div className="w-1/2 overflow-y-auto border-r border-slate-200 p-4">
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Seurat Clustering"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Description *</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this skill do?"
                rows={3}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              />
              <button
                onClick={handleSuggest}
                className="mt-1 text-xs text-primary hover:underline"
              >
                🤖 Auto-suggest parameters
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-700">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
                >
                  <option value="custom">Custom</option>
                  <option value="single-cell">Single Cell</option>
                  <option value="spatial-transcriptomics">Spatial</option>
                  <option value="genomics">Genomics</option>
                  <option value="proteomics">Proteomics</option>
                  <option value="workflows">Workflows</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-700">Tool Type</label>
                <select
                  value={toolType}
                  onChange={(e) => setToolType(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
                >
                  <option value="python">Python</option>
                  <option value="r">R</option>
                  <option value="mixed">Mixed</option>
                </select>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Primary Tool</label>
              <input
                type="text"
                value={primaryTool}
                onChange={(e) => setPrimaryTool(e.target.value)}
                placeholder="e.g., scanpy, Seurat"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Supported Tools (comma-separated)</label>
              <input
                type="text"
                value={supportedTools}
                onChange={(e) => setSupportedTools(e.target.value)}
                placeholder="scanpy, anndata, numpy"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Keywords (comma-separated)</label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="qc, filtering, single-cell"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Dependencies (comma-separated)</label>
              <input
                type="text"
                value={dependencies}
                onChange={(e) => setDependencies(e.target.value)}
                placeholder="scanpy, anndata, matplotlib"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 p-2 text-xs text-red-600">{error}</div>
            )}

            <button
              onClick={handleGenerate}
              disabled={loading}
              className="w-full rounded-lg bg-primary py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
            >
              {loading ? 'Generating...' : 'Generate Skill'}
            </button>
          </div>
        </div>

        {/* Preview */}
        <div className="w-1/2 overflow-hidden bg-slate-50">
          {generatedFiles.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <div className="mb-2 text-3xl">🛠️</div>
                <div className="text-sm text-slate-500">Fill the form and click Generate</div>
              </div>
            </div>
          ) : (
            <div className="flex h-full flex-col">
              <div className="border-b border-slate-200 bg-white px-4 py-2">
                <div className="text-sm font-medium text-slate-800">Generated: {skillId}</div>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                <div className="space-y-3">
                  {generatedFiles.map((file) => (
                    <div key={file.path} className="rounded-lg border border-slate-200 bg-white">
                      <div className="border-b border-slate-100 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600">
                        {file.path}
                      </div>
                      <pre className="overflow-x-auto p-3 text-xs leading-relaxed text-slate-700">
                        <code>{file.content}</code>
                      </pre>
                    </div>
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
