import api from './api'

export interface KnowledgeDocument {
  document_id: string
  title: string
  source?: string
  source_type?: string
  filename?: string
  project_id?: string
  chunk_count: number
  summary?: string
}

export interface KnowledgeSearchResult {
  id: string
  text: string
  score?: number
  metadata?: Record<string, unknown>
}

export interface KnowledgeDocumentDetail {
  document_id: string
  chunks: { id: string; text: string; index?: number }[]
  entities: { id: string; name?: string; type?: string }[]
  edges: { from: string; to: string; type: string; properties?: Record<string, unknown> }[]
}

export interface WikiPage {
  page_id: string
  project_id: string
  title: string
  content: string
  source_document_ids?: string[]
  source_chunk_ids?: string[]
  entity_types?: string[]
  created_at?: string
  updated_at?: string
  created_by?: string
  version?: number
  metadata?: Record<string, unknown>
}

export interface WikiAskResult {
  answer: string
  sources: { type: string; id?: string; title?: string; score?: number }[]
  suggested_pages: string[]
}

export const knowledgeApi = {
  listDocuments: (projectId: string) =>
    api.get<{ documents: KnowledgeDocument[] }>('/knowledge/documents', {
      params: { project_id: projectId },
    }),

  getDocument: (documentId: string) =>
    api.get<KnowledgeDocumentDetail>(`/knowledge/documents/${documentId}`),

  updateDocument: (
    documentId: string,
    projectId: string,
    payload: { title?: string; summary?: string }
  ) =>
    api.patch<{ document_id: string; title?: string; summary?: string }>(
      `/knowledge/documents/${documentId}`,
      payload,
      { params: { project_id: projectId } }
    ),

  ingestUpload: (file: File, projectId: string) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{
      document_id: string
      chunk_count: number
      entity_count: number
      relation_count: number
      already_processed: boolean
    }>('/knowledge/ingest-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { project_id: projectId },
    })
  },

  search: (query: string, projectId: string, topK: number = 5) =>
    api.get<{ results: KnowledgeSearchResult[] }>('/knowledge/search', {
      params: { q: query, project_id: projectId, top_k: topK },
    }),

  // LLM Wiki
  listWikiPages: (projectId: string, q?: string) =>
    api.get<WikiPage[]>('/wiki/pages', {
      params: { project_id: projectId, q },
    }),

  getWikiPage: (pageId: string, projectId: string) =>
    api.get<WikiPage>(`/wiki/pages/${pageId}`, {
      params: { project_id: projectId },
    }),

  createWikiPage: (projectId: string, payload: { title: string; content: string }) =>
    api.post<WikiPage>('/wiki/pages', payload, {
      params: { project_id: projectId },
    }),

  updateWikiPage: (
    pageId: string,
    projectId: string,
    payload: { title?: string; content?: string }
  ) =>
    api.patch<WikiPage>(`/wiki/pages/${pageId}`, payload, {
      params: { project_id: projectId },
    }),

  deleteWikiPage: (pageId: string, projectId: string) =>
    api.delete(`/wiki/pages/${pageId}`, {
      params: { project_id: projectId },
    }),

  askWiki: (question: string, projectId: string, topK: number = 5) =>
    api.post<WikiAskResult>('/wiki/ask', {
      question,
      top_k: topK,
      project_id: projectId,
    }),

  generateWikiPages: (documentId: string, projectId: string) =>
    api.post<WikiPage[]>('/wiki/pages/generate', {
      document_id: documentId,
      project_id: projectId,
    }),
}
