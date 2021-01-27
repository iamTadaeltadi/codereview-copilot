import { render, screen } from '@testing-library/react'

import FormInput from '../FormInput'

describe('FormInput', () => {
  it('associates the label text with the input', () => {
    render(<FormInput label="Repository URL" name="repo_url" />)

    expect(screen.getByLabelText('Repository URL')).toBeInTheDocument()
  })

  it('renders the error message when provided', () => {
    render(<FormInput label="Commit SHA" error="Commit SHA is required" />)

    expect(screen.getByText('Commit SHA is required')).toBeInTheDocument()
  })

  it('uses the explicit id when provided', () => {
    render(<FormInput label="Repository name" id="repo-name-input" />)

    expect(screen.getByLabelText('Repository name')).toHaveAttribute('id', 'repo-name-input')
  })

  it('derives an input id from the label when name is missing', () => {
    render(<FormInput label="Pull Request Number" />)

    expect(screen.getByLabelText('Pull Request Number')).toHaveAttribute('id', 'pull-request-number')
  })
})
