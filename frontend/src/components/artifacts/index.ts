import { registerArtifactRenderer } from './registry'
import {
  AnndataArtifact,
  FileArtifact,
  HtmlArtifact,
  ImageArtifact,
  JsonArtifact,
  PdfArtifact,
  TableArtifact,
} from './renderers'

let registered = false

export function registerDefaultArtifactRenderers(): void {
  if (registered) return
  registered = true
  registerArtifactRenderer('image', ImageArtifact)
  registerArtifactRenderer('table', TableArtifact)
  registerArtifactRenderer('html', HtmlArtifact)
  registerArtifactRenderer('pdf', PdfArtifact)
  registerArtifactRenderer('json', JsonArtifact)
  registerArtifactRenderer('anndata', AnndataArtifact)
  registerArtifactRenderer('file', FileArtifact)
}

// Register built-ins on first import; idempotent for HMR / repeated imports.
registerDefaultArtifactRenderers()

export { ArtifactRenderer } from './ArtifactRenderer'
export { registerArtifactRenderer, resolveArtifactRenderer } from './registry'
export type { Artifact, ArtifactKind } from './types'
export type { ArtifactRendererProps, ArtifactRenderer as ArtifactRendererType } from './registry'
