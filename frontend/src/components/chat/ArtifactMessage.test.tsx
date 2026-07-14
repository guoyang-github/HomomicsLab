import '@testing-library/jest-dom'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ArtifactMessage } from './ArtifactMessage'

describe('ArtifactMessage', () => {
  it('renders an inline JSON artifact card', () => {
    render(
      <ArtifactMessage
        content={{
          kind: 'json',
          name: 'metrics.json',
          data: { ari: 0.91 },
        }}
      />
    )
    expect(screen.getByText('metrics.json')).toBeInTheDocument()
    expect(screen.getByText('json')).toBeInTheDocument()
    expect(screen.getByText(/"ari": 0.91/)).toBeInTheDocument()
  })

  it('renders multiple artifacts from an artifacts array', () => {
    render(
      <ArtifactMessage
        content={{
          artifacts: [
            { kind: 'json', name: 'a.json', data: {} },
            { kind: 'anndata', name: 'result.h5ad' },
          ],
        }}
      />
    )
    expect(screen.getByText('a.json')).toBeInTheDocument()
    expect(screen.getByText('AnnData：result.h5ad')).toBeInTheDocument()
  })

  it('shows a fullscreen button for HTML artifacts', () => {
    render(
      <ArtifactMessage
        content={{
          kind: 'html',
          name: 'report.html',
          url: 'https://example.com/report.html',
        }}
      />
    )
    expect(screen.getByTitle('Fullscreen')).toBeInTheDocument()
    expect(screen.getByTitle('Download')).toBeInTheDocument()
  })
})
