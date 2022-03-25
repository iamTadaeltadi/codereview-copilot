import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RepoRegistration from '../index'

const dispatchMock = vi.fn()
const navigateMock = vi.fn()
const createRepositoryActionMock = vi.fn((payload: any) => ({
  type: 'repos/createRepository',
  payload,
}))
const selectorState = {
  repos: {
    status: 'idle',
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/RepoAction', () => ({
  createRepositoryAction: (payload: any) => createRepositoryActionMock(payload),
}))

vi.mock('react-redux', async () => {
  const actual = await vi.importActual<any>('react-redux')
  return {
    ...actual,
    useDispatch: () => dispatchMock,
    useSelector: (fn: any) => fn(selectorState),
  }
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

describe('RepoRegistration page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    navigateMock.mockReset()
    createRepositoryActionMock.mockClear()
    selectorState.repos = {
      status: 'idle',
      error: null,
    }
  })

  it('parses preview values and submits repository creation payload', async () => {
    dispatchMock.mockReturnValue({
      unwrap: () => Promise.resolve({ id: 42 }),
    })

    render(
      <MemoryRouter>
        <RepoRegistration />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/repository name/i), {
      target: { value: 'owner/repo' },
    })
    fireEvent.change(screen.getByLabelText(/repository url/i), {
      target: { value: 'https://github.com/owner/repo' },
    })
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: 'Code review automation' },
    })
    fireEvent.change(screen.getByLabelText(/coding standards/i), {
      target: { value: 'DRY, SOLID' },
    })
    fireEvent.change(screen.getByLabelText(/code metrics/i), {
      target: { value: 'complexity, testability' },
    })
    fireEvent.change(
      document.querySelector('select[name="llm_preference"]') as HTMLSelectElement,
      {
        target: { value: 'gpt-4o' },
      },
    )

    expect(screen.getByText(/Parsed standards: DRY, SOLID/i)).toBeInTheDocument()
    expect(screen.getByText(/Parsed metrics: complexity, testability/i)).toBeInTheDocument()

    fireEvent.submit(screen.getByRole('button', { name: /register repository/i }).closest('form')!)

    await waitFor(() => {
      expect(createRepositoryActionMock).toHaveBeenCalledWith({
        repoName: 'owner/repo',
        repoUrl: 'https://github.com/owner/repo',
        description: 'Code review automation',
        codingStandards: ['DRY', 'SOLID'],
        codeMetrics: ['complexity', 'testability'],
        llmPreference: 'gpt-4o',
      })
      expect(navigateMock).toHaveBeenCalledWith('/repos/42')
    })
  })

  it('renders loading and error states from the repo slice', () => {
    selectorState.repos = {
      status: 'loading',
      error: 'Creation failed',
    }

    render(
      <MemoryRouter>
        <RepoRegistration />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: /registering/i })).toBeDisabled()
    expect(screen.getByText('Creation failed')).toBeInTheDocument()
  })
})
