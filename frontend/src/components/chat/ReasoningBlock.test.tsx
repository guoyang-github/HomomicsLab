import '@testing-library/jest-dom'
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ReasoningBlock } from './ReasoningBlock'

describe('ReasoningBlock', () => {
  it('renders the header collapsed by default and hides the reasoning text', () => {
    render(<ReasoningBlock reasoning="step by step analysis" />)
    const toggle = screen.getByRole('button', { name: /Thinking/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('step by step analysis')).not.toBeInTheDocument()
  })

  it('expands on click and shows the reasoning text', () => {
    render(<ReasoningBlock reasoning="step by step analysis" />)
    fireEvent.click(screen.getByRole('button', { name: /Thinking/ }))
    expect(screen.getByText('step by step analysis')).toBeInTheDocument()
  })

  it('renders nothing for blank reasoning', () => {
    const { container } = render(<ReasoningBlock reasoning="   " />)
    expect(container).toBeEmptyDOMElement()
  })
})
