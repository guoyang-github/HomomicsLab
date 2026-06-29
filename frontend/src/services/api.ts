import axios from 'axios'
import type { SendMessageRequest, SendMessageResponse, LlmConfigOut, TestConnectionOut, Project, FileUploadResponse, ReportSummary, ReportDetail, ReportHtmlExport, ReportMarkdownExport, SkillSummary, SkillDetail, ImportSkillRequest, PromoteSkillRequest, PromoteSkillResponse, ImportSkillResponse, SkillValidationResponse, SkillTestResponse, SkillLockResponse, DomainListing, DomainPreview, ExportDomainResponse, ImportDomainResponse, CreateVizSessionRequest, CreateVizSessionResponse, RenderVizRequest, RenderVizResponse, FigureItem } from '@/types/api'
import type { ChatMessage } from '@/types/chat'
import type { ChatSession } from '@/stores/chatStore'
import type { PlanModification } from '@/stores/planStore'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const chatApi = {
  sendMessage: (data: SendMessageRequest) =>
    api.post<SendMessageResponse>('/chat/send', data),

  getMessages: (sessionId: string) =>
    api.get<ChatMessage[]>(`/chat/messages?session_id=${sessionId}`),

  listSessions: (projectId?: string) =>
    api.get<ChatSession[]>('/chat/sessions', { params: projectId ? { project_id: projectId } : undefined }),

  respondToHITL: (data: { session_id: string; task_id: string; choice: string; parameters?: Record<string, unknown>; remember?: boolean }) =>
    api.post('/chat/hitl/respond', data),

  respondToDebate: (data: { session_id: string; debate_id: string; choice_id: string; parameters?: Record<string, unknown> }) =>
    api.post('/chat/debate/respond', data),

  regenerate: (data: SendMessageRequest) =>
    api.post<SendMessageResponse>('/chat/regenerate', data),

  submitFeedback: (data: { message_id: string; rating: 'positive' | 'negative'; comment?: string }) =>
    api.post('/chat/feedback', data),
}

export const planApi = {
  approve: (plan_id: string) =>
    api.post(`/plan/${plan_id}/approve`, { approved: true, modifications: [] }),

  reject: (plan_id: string) =>
    api.post(`/plan/${plan_id}/reject`),

  modify: (plan_id: string, approved: boolean, modifications: PlanModification[]) =>
    api.post(`/plan/${plan_id}/modify`, { approved, modifications }),

  getPlan: (plan_id: string) =>
    api.get(`/plan/${plan_id}`),

  listPlans: (session_id: string) =>
    api.get(`/plan/session/${session_id}`),

  diff: (plan_id: string, other_plan_id?: string) =>
    api.get(`/plan/${plan_id}/diff`, { params: other_plan_id ? { other: other_plan_id } : undefined }),

  getJob: (plan_id: string) =>
    api.get(`/plan/${plan_id}/job`),

  saveTemplate: (plan_id: string, name: string) =>
    api.post(`/plan/${plan_id}/template`, { name }),

  listTemplates: () =>
    api.get('/plan/templates'),

  loadTemplate: (template_id: string) =>
    api.post(`/plan/template/${template_id}/load`),
}

export const projectApi = {
  createProject: (data: { name: string; description?: string }) =>
    api.post<Project>('/projects', data),

  listProjects: () =>
    api.get<Project[]>('/projects'),

  exportROCrate: (projectId: string) =>
    api.post(
      `/projects/${projectId}/export/rocrate`,
      {},
      { responseType: 'blob' }
    ),
}

export interface FileEntry {
  name: string
  type: 'file' | 'directory'
  path: string
  size: number | null
  modified_at: number
}

export interface FileListResponse {
  project_id: string
  path: string
  entries: FileEntry[]
}

export interface FileReadResponse {
  project_id: string
  path: string
  mime_type: string
  size: number
  encoding: 'utf-8' | 'base64'
  content: string
}

export const fileApi = {
  listFiles: (projectId: string, path: string = '') =>
    api.get<FileListResponse>(`/files/list?project_id=${projectId}&path=${encodeURIComponent(path)}`),

  readFile: (projectId: string, path: string) =>
    api.get<FileReadResponse>(`/files/read?project_id=${projectId}&path=${encodeURIComponent(path)}`),

  uploadFile: (file: File, projectId: string) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<FileUploadResponse>(`/files/upload?project_id=${projectId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const reportApi = {
  listReports: () =>
    api.get<ReportSummary[]>('/reports/list'),

  getReport: (reportId: string) =>
    api.get<ReportDetail>(`/reports/${reportId}`),

  createReport: (data: { title: string; project_name?: string; analysis_type?: string; tags?: string[] }) =>
    api.post<{ report_id: string; title: string }>('/reports/create', data),

  exportHtml: (reportId: string) =>
    api.get<ReportHtmlExport>(`/reports/${reportId}/html`),

  exportMarkdown: (reportId: string) =>
    api.get<ReportMarkdownExport>(`/reports/${reportId}/markdown`),
}

export const skillsApi = {
  listSkills: () =>
    api.get<SkillSummary[]>('/skills/'),

  searchSkills: (query: string) =>
    api.get<SkillSummary[]>('/skills/search', { params: { q: query } }),

  getSkill: (skillId: string) =>
    api.get<SkillDetail>(`/skills/${skillId}`),

  importSkill: (data: ImportSkillRequest) =>
    api.post<ImportSkillResponse>('/skills/import', data),

  promoteSkill: (data: PromoteSkillRequest) =>
    api.post<PromoteSkillResponse>('/skills/promote', data),

  updateSkill: (skillId: string, data: ImportSkillRequest) =>
    api.post<ImportSkillResponse>(`/skills/${skillId}/update`, data),

  removeSkill: (skillId: string, namespace: string = 'default') =>
    api.delete(`/skills/${skillId}`, { params: { namespace } }),

  enableSkill: (skillId: string, namespace: string = 'default') =>
    api.post(`/skills/${skillId}/enable`, null, { params: { namespace } }),

  disableSkill: (skillId: string, namespace: string = 'default') =>
    api.post(`/skills/${skillId}/disable`, null, { params: { namespace } }),

  validateSkill: (skillId: string, namespace: string = 'default') =>
    api.post<SkillValidationResponse>(`/skills/${skillId}/validate`, null, { params: { namespace } }),

  testSkill: (skillId: string, namespace: string = 'default') =>
    api.post<SkillTestResponse>(`/skills/${skillId}/test`, null, { params: { namespace } }),

  lockSkills: (projectId: string) =>
    api.post<SkillLockResponse>('/skills/lock', null, { params: { project_id: projectId } }),
}

export const domainsApi = {
  listDomains: () =>
    api.get<DomainListing[]>('/domains/'),

  previewDomain: (domainId: string) =>
    api.get<DomainPreview>(`/domains/${domainId}/preview`),

  exportDomain: (domainId: string, targetDir?: string) =>
    api.post<ExportDomainResponse>(`/domains/${domainId}/export`, targetDir ? { target_dir: targetDir } : undefined),

  importDomain: (source: string) =>
    api.post<ImportDomainResponse>('/domains/import', { source }),
}

export const vizApi = {
  createSession: (data: CreateVizSessionRequest) =>
    api.post<CreateVizSessionResponse>('/viz/sessions', data),

  render: (sessionId: string, data: RenderVizRequest) =>
    api.post<RenderVizResponse>(`/viz/sessions/${sessionId}/render`, data),

  listFigures: (projectId: string) =>
    api.get<FigureItem[]>(`/projects/${projectId}/figures`),

  deleteFigure: (projectId: string, figureId: string) =>
    api.delete(`/projects/${projectId}/figures/${figureId}`),
}

export interface LlmConfigUpdate {
  provider: string
  model: string
  fallback_models?: string[]
  base_url?: string
  api_key?: string
  temperature: number
  max_tokens: number
}

export const settingsApi = {
  getLlmConfig: () => api.get<LlmConfigOut>('/settings/llm'),
  updateLlmConfig: (data: LlmConfigUpdate) =>
    api.put<LlmConfigOut>('/settings/llm', data),
  testLlmConnection: (data?: LlmConfigUpdate) =>
    api.post<TestConnectionOut>('/settings/llm/test', data),
}

export default api
