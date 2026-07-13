export type ArtifactKind =
  | 'image'
  | 'table'
  | 'html'
  | 'pdf'
  | 'json'
  | 'anndata'
  | 'plotly'
  | 'file'

export interface Artifact {
  kind?: ArtifactKind | string
  mime?: string
  name?: string
  path?: string
  url?: string
  preview_url?: string
  data?: unknown
  size?: number
}
