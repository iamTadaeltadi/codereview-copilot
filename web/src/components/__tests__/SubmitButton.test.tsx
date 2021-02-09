import { render, screen } from '@testing-library/react'
import { FiTrash2 } from 'react-icons/fi'

import SubmitButton from '../SubmitButton'

describe('SubmitButton', () => {
  it('disables itself while loading', () => {
    render(<SubmitButton loading>Save review</SubmitButton>)

    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(screen.getByText('Processing...')).toBeInTheDocument()
  })

  it('renders its children when not loading', () => {
    render(<SubmitButton variant="danger">Delete review</SubmitButton>)

    expect(screen.getByRole('button', { name: 'Delete review' })).toBeInTheDocument()
  })

  it('keeps the button disabled when disabled is explicitly passed', () => {
    render(<SubmitButton disabled>Disabled review</SubmitButton>)

    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('renders the optional icon when provided', () => {
    const { container } = render(<SubmitButton icon={FiTrash2}>Remove</SubmitButton>)

    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument()
    expect(container.querySelector('svg')).toBeTruthy()
  })
})
