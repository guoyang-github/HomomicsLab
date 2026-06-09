import type { ChatMessage } from './chat'
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
}

export interface SendMessageResponse {
  response: string
  task_tree: { tasks: TaskNode[] }
  messages: ChatMessage[]
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
  category: string
  runtime_type: string
  primary_tool: string
}

export interface SkillDetail extends SkillSummary {
  version: string
  supported_tools: string[]
  keywords: string[]
  dependencies: string[]
  scripts_dir: string | null
  source: string
}
