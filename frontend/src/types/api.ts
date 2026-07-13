import type { ChatMessage, PlanRequestContent } from './chat'
import type { TaskNode } from './tasks'

export interface Project {
  id: string
  name: string
  description: string
  template_id?: string
  created_at: string
  updated_at: string
}

export interface AnalysisTemplate {
  template_id: string
  name: string
  description: string
  domain: string
  applicable_intents: string[]
  tags: string[]
  phase_defaults: Record<string, Record<string, unknown>>
  preferred_skills: Record<string, string>
  default_parameters: Record<string, unknown>
  sop_ids: string[]
  data_sources: Record<string, unknown>[]
  icon?: string
  version: string
}

export interface SendMessageRequest {
  project_id: string
  session_id: string
  message: string
  plan_mode?: boolean
}

export interface SendMessageResponse {
  response: string
  task_tree: { tasks: TaskNode[] }
  messages: ChatMessage[]
  attachments: { type: string; content: Record<string, unknown> }[]
  job_id: string | null
  plan_id: string | null
  plan: PlanRequestContent['plan'] | null
  status: string
}

export interface LlmConfigOut {
  provider: string | null
  model: string | null
  fallback_models: string[]
  base_url: string | null
  api_key: string | null
  api_key_set: boolean
  temperature: number
  max_tokens: number
}

export interface TestConnectionOut {
  ok: boolean
  provider: string | null
  model: string | null
  error: string | null
}

export interface SystemSettingsOut {
  skill_sandbox_backend: string
  enable_semantic_memory: boolean
  semantic_search_model: string | null
  session_ttl_days: number
  default_job_timeout_seconds: number
  max_skill_timeout_seconds: number
  result_inline_size_limit_bytes: number
  max_llm_cost_per_request_usd: number | null
  monthly_budget_usd: number | null
  skill_hot_reload_enabled: boolean
  open_exploration_mode_enabled: boolean
}

export interface SystemSettingsUpdate {
  skill_sandbox_backend?: string
  enable_semantic_memory?: boolean
  semantic_search_model?: string
  session_ttl_days?: number
  default_job_timeout_seconds?: number
  max_skill_timeout_seconds?: number
  result_inline_size_limit_bytes?: number
  max_llm_cost_per_request_usd?: number
  monthly_budget_usd?: number
  skill_hot_reload_enabled?: boolean
  open_exploration_mode_enabled?: boolean
}

export interface HealthStatusResponse {
  status: string
  version: string
  llm_configured: boolean
  llm_provider: string | null
  llm_model: string | null
}

export interface ExecutionTraceNode {
  node_id: string
  parent_id?: string | null
  node_type: string
  name: string
  status: string
  started_at?: string
  ended_at?: string | null
  inputs?: Record<string, unknown> | null
  outputs?: Record<string, any> | null
  error?: string | null
  logs?: string[]
  metadata?: Record<string, unknown>
}

export interface ExecutionTrace {
  trace_id: string
  session_id?: string | null
  project_id?: string | null
  status: string
  started_at?: string
  ended_at?: string | null
  error_message?: string | null
  nodes: ExecutionTraceNode[]
}

export interface ExecutionStatusResponse {
  job_id: string
  status: string
  mode?: string | null
  created_at?: string | null
  updated_at?: string | null
  error_message?: string | null
  latest_state?: Record<string, any> | null
}

export interface ExecutionProgress {
  total: number
  pending: number
  running: number
  completed: number
  failed: number
  awaiting_human: number
  percent: number
}

export interface ExecutionTasksResponse {
  job_id: string
  status: string
  tasks: TaskNode[]
  progress: ExecutionProgress
}

export interface CancelJobResponse {
  job_id: string
  status: string
  cancelled: boolean
}

export interface SkillGeneratorInput {
  name: string
  description: string
  required: boolean
  default?: string
}

export interface SkillGeneratorSuggestRequest {
  description: string
}

export interface SkillGeneratorSuggestResponse {
  tool_type: string
  category: string
  keywords: string[]
}

export interface SkillGeneratorGenerateRequest {
  name: string
  description: string
  category: string
  tool_type: string
  primary_tool: string
  supported_tools: string[]
  keywords: string[]
  dependencies: string[]
  inputs: SkillGeneratorInput[]
  outputs: string[]
}

export interface SkillGeneratorGenerateResponse {
  skill_id: string
  files: Record<string, string>
}

export interface FileUploadResponse {
  filename: string
  path: string
  size: number
}

export interface ReportSummary {
  id: string
  title: string
  project_name: string
  analysis_type: string
  created_at: string
  step_count: number
  section_count: number
}

export interface ReportFigure {
  image_base64: string
  caption: string
  figure_type: string
  width: number
  height: number
}

export interface ReportTable {
  headers: string[]
  rows: unknown[][]
  caption: string
}

export interface ReportSection {
  title: string
  type: string
  content: string
  figures: ReportFigure[]
  tables: ReportTable[]
  metadata: Record<string, unknown>
}

export interface AnalysisStep {
  step_number: number
  name: string
  description: string
  skill_id: string
  status: string
  duration_seconds: number | null
  started_at: string | null
  completed_at: string | null
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  notes: string
}

export interface ReportMetadata {
  project_name: string
  analysis_type: string
  author: string
  created_at: string
  version: string
  tags: string[]
  parameters: Record<string, unknown>
}

export interface ReportDetail {
  id: string
  title: string
  metadata: ReportMetadata
  sections: ReportSection[]
  analysis_steps: AnalysisStep[]
  summary: string
}

export interface ReportHtmlExport {
  html: string
  report_id: string
  title: string
}

export interface ReportMarkdownExport {
  markdown: string
  report_id: string
  title: string
}

export interface SkillSummary {
  id: string
  name: string
  description: string
  version: string
  category: string
  runtime_type: string
  primary_tool: string
  source: string
  namespace: string
  enabled: boolean
}

export interface SkillDetail extends SkillSummary {
  version: string
  supported_tools: string[]
  keywords: string[]
  dependencies: string[]
  scripts_dir: string | null
  source: string
  namespace: string
  enabled: boolean
}

export interface ImportSkillRequest {
  source: string
  namespace?: string
  skill_id?: string
  enable?: boolean
}

export interface PromoteSkillRequest {
  source_dir: string
  skill_id?: string
  name?: string
  description?: string
  category?: string
  namespace?: string
  trusted?: boolean
}

export interface PromoteSkillResponse {
  skill_id: string
  name: string
  namespace: string
  source_dir: string
  trusted: boolean
}

export interface ImportSkillResponse {
  skill_id: string
  name: string
  version: string
  namespace: string
  enabled: boolean
}

export interface SkillValidationResponse {
  valid: boolean
  errors: string[]
  warnings: string[]
}

export interface SkillTestResponse {
  success: boolean
  stdout: string
  stderr: string
  exit_code: number | null
  tests_run: number
  tests_passed: number
}

export interface SkillLockResponse {
  project_id: string
  locked_at: string
  skills: Record<string, string>
}

export interface CreateVizSessionRequest {
  project_id: string
  source_filename: string
  table_type_hint?: string | null
}

export interface CreateVizSessionResponse {
  session_id: string
  success: boolean
  outputs: Record<string, unknown>
  interpretation: string
}

export interface RenderVizRequest {
  project_id: string
  action: 'stat_test' | 'render' | 'render_plotly' | 'vision_edit' | 'full_pipeline'
  params: Record<string, unknown>
}

export interface RenderVizResponse {
  success: boolean
  outputs: Record<string, unknown>
  artifacts?: Array<{ type: string; path: string; mime: string }>
  interpretation?: string
  error?: string
}

export interface FigureItem {
  figure_id: string
  formats: Record<string, string>
  preview_url: string
  created_at: string
}

export interface DomainListing {
  domain_id: string
  name: string
  description: string
  version: string
  author?: string
  tags?: string[]
  source: string
}

export interface DomainPreview {
  domain_id: string
  name: string
  description: string
  version: string
  author: string
  orchestrator_skills: string[]
  phases: Array<{
    id: string
    required?: boolean
    description?: string
    skills?: string[]
    default_skill?: string
    [key: string]: any
  }>
  phase_transitions: Array<{
    from: string
    to: string
    type?: string
    [key: string]: any
  }>
  intents: Array<{
    type: string
    description?: string
    keywords?: string[]
    [key: string]: any
  }>
  skills: string[]
  roles: Array<{
    role_id: string
    name?: string
    allowed_skills?: string[]
    [key: string]: any
  }>
  sops: Array<{
    id: string
    title?: string
    steps?: string[]
    [key: string]: any
  }>
  code_templates: Record<string, { language?: string; skeleton?: string }>
}

export interface ExportDomainResponse {
  exported_to: string
  domain_id: string
}

export interface ImportDomainResponse {
  imported: boolean
  domain_id: string
  domain_dir: string
}

export interface PlotDataRequest {
  plot_type: 'umap' | 'heatmap' | 'violin' | 'bar' | 'scatter' | 'histogram'
  data: Record<string, unknown>
  title?: string
  width?: number
  height?: number
}

export interface PlotDataResponse {
  data: unknown[]
  layout: Record<string, unknown>
  plot_type: string
}

export interface PlotTypeInfo {
  type: string
  description: string
}

export type MCPTransport = 'embedded' | 'stdio' | 'sse'

export interface MCPServer {
  id: string
  name: string
  description: string
  transport: MCPTransport
  package?: string | null
  command?: string | null
  args: string[]
  url?: string | null
  env: Record<string, string>
  category: string
  enabled: boolean
  installed: boolean
  trusted: boolean
  builtin: boolean
  install_status?: string | null
  tools: Record<string, unknown>[]
}

export interface MCPServerCreate {
  id: string
  name: string
  description?: string
  transport: MCPTransport
  package?: string
  command?: string
  args?: string[]
  url?: string
  env?: Record<string, string>
  category?: string
}

export interface MCPServerHealthResponse {
  id: string
  status: 'ok' | 'error'
  tool_count: number
  tools: Record<string, unknown>[]
  error?: string
}

export interface LineageNode {
  node_id: string
  path: string
  type: 'raw' | 'intermediate' | 'output' | 'data'
  checksum: string
  created_by_task: string
  created_at: string
  metadata?: Record<string, unknown>
}

export interface LineageEdge {
  from_node: string
  to_node: string
  transform_type: string
  transform_id: string
  metadata?: Record<string, unknown>
}

export interface LineageGraph {
  nodes: LineageNode[]
  edges: LineageEdge[]
}
