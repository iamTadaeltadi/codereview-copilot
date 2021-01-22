import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import ErrorMessage from '../ErrorMessage'

describe('ErrorMessage', () => {
  it('renders title and message', () => {
    render(<ErrorMessage title="Load failed" message="Unable to fetch reviews" />)

    expect(screen.getByText('Load failed')).toBeInTheDocument()
    expect(screen.getByText('Unable to fetch reviews')).toBeInTheDocument()
  })

  it('calls onRetry when retry button is clicked', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()

    render(<ErrorMessage message="Retry me" onRetry={onRetry} />)
    await user.click(screen.getByRole('button', { name: 'Try Again' }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('uses the default title when no title is supplied', () => {
    render(<ErrorMessage message="Default title path" />)

    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('does not render a retry button when onRetry is missing', () => {
    render(<ErrorMessage message="Read only" />)

    expect(screen.queryByRole('button', { name: 'Try Again' })).not.toBeInTheDocument()
  })
})
