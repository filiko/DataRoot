export const API_BASE = import.meta.env.VITE_API_URL || ''

export function getApiUrl(path: string): string {
  if (API_BASE.startsWith('http')) {
    return `${API_BASE}${path}`
  }
  return `${window.location.origin}${API_BASE}${path}`
}

export const API = {
  ingest: () => getApiUrl('/ingest/spreadsheet'),
  schema: (_id: string) => getApiUrl(`/schema/${_id}`),
  health: () => getApiUrl('/health'),
  exportSql: (_id: string) => getApiUrl(`/schema/${_id}/export/sql`),
  exportMermaid: (_id: string) => getApiUrl(`/schema/${_id}/export/mermaid`),
  exportDbml: (_id: string) => getApiUrl(`/schema/${_id}/export/dbml`),
  exportPen: (_id: string) => getApiUrl(`/schema/${_id}/export/pen`),
  applyProposal: (_id: string) => getApiUrl(`/schema/${_id}/apply-proposal`),
  analyze: (_id: string) => getApiUrl(`/schema/${_id}/analyze`),
  chat: () => getApiUrl(`/llm/chat`),
  ops: (_id: string) => getApiUrl(`/projects/${_id}/ops`),
  layout: (_id: string) => getApiUrl(`/schema/${_id}/layout`),
  validate: (_id: string) => getApiUrl(`/schema/${_id}/validate`),
  deleteEntity: (_projectId: string, _entityId: string) => getApiUrl(`/schema/${_projectId}/entity/${_entityId}`),
  deleteRelationship: (_projectId: string, _relId: string) => getApiUrl(`/schema/${_projectId}/relationship/${_relId}`),
  blank: () => getApiUrl('/schema/blank'),
  example: () => getApiUrl('/schema/example'),
  morsat0Exercise: () => getApiUrl('/schema/morsat0-exercise'),
  claudeEval: () => getApiUrl('/schema/claude-eval'),
  repoAnalysis: () => getApiUrl('/schema/repo-analysis'),
  repoAnalysisUpload: () => getApiUrl('/schema/repo-analysis/upload'),
  projects: (id: string) => getApiUrl(`/projects/${id}`),
  openProject: () => getApiUrl('/projects/open'),
  saveProject: () => getApiUrl('/projects/save'),
  importProject: () => getApiUrl('/projects/import'),
  deleteProject: (id: string) => getApiUrl(`/projects/${id}`),
  projectList: () => getApiUrl('/projects'),
  projectRevision: (id: string) => getApiUrl(`/projects/${id}/revision`),
  waitlist: () => getApiUrl('/waitlist'),
  ask: () => getApiUrl('/ask'),
  signup: () => getApiUrl('/auth/signup'),
  login: () => getApiUrl('/auth/login'),
  logout: () => getApiUrl('/auth/logout'),
  me: () => getApiUrl('/auth/me'),
  createInvite: (projectId: string) => getApiUrl(`/projects/${projectId}/invites`),
  acceptInvite: (token: string) => getApiUrl(`/invites/${token}/accept`),
  peekInvite: (token: string) => getApiUrl(`/invites/${token}`),
}
