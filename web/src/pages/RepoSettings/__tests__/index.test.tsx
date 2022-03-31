import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RepoSettingsPage from '../index'

const dispatchMock = vi.fn()
const unwrapMock = vi.fn().mockResolvedValue(undefined)
const fetchRepoDetailsActionMock = vi.fn((repoId: number) => ({
  type: 'repos/fetchDetails',
  payload: repoId,
}))
const updateRepoSettingsActionMock = vi.fn((payload: any) => ({
  type: 'repos/updateSettings',
  payload,
}))
const selectorState = {
  repos: {
    currentRepo: null as any,
    status: 'idle',
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/RepoAction', () => ({
  fetchRepoDetailsAction: (repoId: number) => fetchRepoDetailsActionMock(repoId),
  updateRepoSettingsAction: (payload: any) => updateRepoSettingsActionMock(payload),
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
    useParams: () => ({ repoId: '12' }),
  }
})

describe('RepoSettings page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    dispatchMock.mockImplementation((action: any) => {
      if (action?.type === 'repos/updateSettings') {
        return { unwrap: unwrapMock }
      }
      return action
    })
    unwrapMock.mockClear()
    fetchRepoDetailsActionMock.mockClear()
    updateRepoSettingsActionMock.mockClear()
    selectorState.repos = {
      currentRepo: null,
      status: 'idle',
      error: null,
    }
  })

  it('populates editable fields and submits parsed settings to the backend action', async () => {
    selectorState.repos = {
      status: 'succeeded',
      error: null,
      currentRepo: {
        id: 12,
        name: 'graph-review-engine',
        description: 'Repository automation',
        settings: {
          codeStandards: ['DRY', 'SOLID'],
          evaluationMetrics: ['complexity'],
          llmModel: 'gpt-4o',
          webhookUrl: 'https://example.com/webhook',
        },
      },
    }

    render(
      <MemoryRouter>
        <RepoSettingsPage />
      </MemoryRouter>,
    )

    expect(fetchRepoDetailsActionMock).toHaveBeenCalledWith(12)
    expect(screen.getByDisplayValue('graph-review-engine')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Repository automation')).toBeInTheDocument()
    expect(screen.getByDisplayValue('DRY, SOLID')).toBeInTheDocument()
    expect(screen.getByText(/parsed standards: dry, solid/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/repository name/i), {
      target: { value: 'graph-review-platform' },
    })
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: 'Updated description' },
    })
    fireEvent.change(screen.getByLabelText(/coding standards/i), {
      target: { value: 'SOLID, security, tests' },
    })
    fireEvent.change(screen.getByLabelText(/evaluation metrics/i), {
      target: { value: 'maintainability, coverage' },
    })
    fireEvent.change(screen.getByLabelText(/preferred model/i), {
      target: { value: 'claude-3.5-sonnet' },
    })

    fireEvent.click(screen.getByRole('button', { name: /save settings/i }))

    await waitFor(() => {
      expect(updateRepoSettingsActionMock).toHaveBeenCalledWith({
        repoId: 12,
        settings: {
          codeStandards: ['SOLID', 'security', 'tests'],
          evaluationMetrics: ['maintainability', 'coverage'],
          llmModel: 'claude-3.5-sonnet',
          webhookUrl: 'https://example.com/webhook',
          webhookEnabled: true,
        },
        metadata: {
          name: 'graph-review-platform',
          description: 'Updated description',
        },
      })
    })
    expect(unwrapMock).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/parsed metrics: maintainability, coverage/i)).toBeInTheDocument()
  })

  it('renders loading, failure, retry, inline error, and saving states', () => {
    selectorState.repos = {
      currentRepo: null,
      status: 'loading',
      error: null,
    }

    const { rerender } = render(
      <MemoryRouter>
        <RepoSettingsPage />
