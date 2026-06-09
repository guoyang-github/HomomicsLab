import axios from 'axios'
import type { SendMessageRequest, SendMessageResponse, Project, FileUploadResponse, ReportSummary, ReportDetail, ReportHtmlExport, ReportMarkdownExport, SkillSummary, SkillDetail } from '@/types/api'
import type { ChatMessage } from '@/types/chat'

const API_BASE = '/api'

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

  respondToHITL: (data: { session_id: string; task_id: string; choice: string; parameters?: Record<string, unknown> }) =>
    api.post('/chat/hitl/respond', data),
}

export const projectApi = {
  createProject: (data: { name: string; description?: string }) =>
    api.post<Project>('/projects', data),

  listProjects: () =>
    api.get<Project[]>('/projects'),
}

export const fileApi = {
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
}

export default api
