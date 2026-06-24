import type { ChatMessage, PlanRequestContent } from './chat'
import type { TaskNode } from './tasks'

export interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
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
