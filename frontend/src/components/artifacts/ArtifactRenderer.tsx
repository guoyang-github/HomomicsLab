import { resolveArtifactRenderer } from './registry'
import { FileArtifact } from './renderers'
import type { ArtifactRendererProps } from './registry'

export function ArtifactRenderer({ artifact, projectId }: ArtifactRendererProps) {
  const Renderer = resolveArtifactRenderer(artifact) || FileArtifact
  return <Renderer artifact={artifact} projectId={projectId} />
}
