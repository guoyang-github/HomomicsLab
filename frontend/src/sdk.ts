/**
 * Typed frontend SDK for HomomicsLab.
 *
 * This module is the single entry point the UI uses to talk to the backend.
 * It isolates React components from FastAPI wire shapes and lets the backend
 * evolve (new runtimes, MCP tools, job backends) without UI changes.
 */
export {
  default as http,
  setApiBaseUrl,
  chatApi,
  planApi,
  projectApi,
  analysisTemplateApi,
  fileApi,
  lineageApi,
  reportApi,
  skillsApi,
  domainsApi,
  vizApi,
  settingsApi,
  healthApi,
  executionApi,
  skillGeneratorApi,
  mcpApi,
} from '@/services/api'

export type * from '@/types/api'
