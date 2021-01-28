import { render, screen } from '@testing-library/react'

import LoadingSpinner from '../LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders the provided message', () => {
    render(<LoadingSpinner message="Reviewing changes" />)

    expect(screen.getByText('Reviewing changes')).toBeInTheDocument()
  })

  it('omits the message element when message is empty', () => {
    const { container } = render(<LoadingSpinner message="" size="lg" />)

    expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    expect(container.querySelector('.w-16.h-16')).toBeTruthy()
  })

  it('uses the default loading message when none is provided', () => {
    render(<LoadingSpinner />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('applies the requested size class for small spinners', () => {
    const { container } = render(<LoadingSpinner size="sm" />)

    expect(container.querySelector('.w-8.h-8')).toBeTruthy()
  })
})
