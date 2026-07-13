import type { ComponentType } from 'react'
import type { Artifact } from './types'

export interface ArtifactRendererProps {
  artifact: Artifact
  projectId?: string
}

export type ArtifactRenderer = ComponentType<ArtifactRendererProps>

const registry = new Map<string, ArtifactRenderer>()

export function registerArtifactRenderer(kind: string, renderer: ArtifactRenderer): void {
  registry.set(kind, renderer)
}

export function resolveArtifactRenderer(artifact: Artifact): ArtifactRenderer | undefined {
  if (artifact.kind && registry.has(artifact.kind)) {
    return registry.get(artifact.kind)
  }
  const mime = artifact.mime || ''
  if (mime.startsWith('image/')) return registry.get('image')
  if (mime === 'text/csv' || mime === 'text/tab-separated-values') return registry.get('table')
  if (mime === 'text/html') return registry.get('html')
  if (mime === 'application/pdf') return registry.get('pdf')
  if (mime === 'application/json') return registry.get('json')
  return registry.get('file')
}
