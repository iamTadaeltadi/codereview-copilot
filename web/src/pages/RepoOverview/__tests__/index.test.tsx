import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RepoOverview from '../index'

const dispatchMock = vi.fn()
const navigateMock = vi.fn()
const fetchRepoDetailsActionMock = vi.fn((repoId: number) => ({
  type: 'repos/fetchRepoDetails',
  payload: repoId,
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
    useNavigate: () => navigateMock,
  }
})

describe('RepoOverview page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    navigateMock.mockReset()
    fetchRepoDetailsActionMock.mockClear()
    selectorState.repos = {
      currentRepo: null,
      status: 'idle',
      error: null,
    }
  })

  it('loads repo details and renders repository overview content', () => {
    selectorState.repos = {
      currentRepo: {
        id: 12,
        name: 'graph-review-engine',
        description: 'Repository automation',
        stats: {
          pullRequests: 8,
          commits: 31,
          contributors: 5,
          reviewScore: '93%',
        },
        activities: [
          {
            id: 'a1',
            action: 'opened a pull request',
            timestamp: 'today',
            user: { name: 'Ada', avatar: '/ada.png' },
          },
        ],
      },
      status: 'succeeded',
      error: null,
    }

    render(
      <MemoryRouter>
        <RepoOverview />
      </MemoryRouter>,
    )

    expect(fetchRepoDetailsActionMock).toHaveBeenCalledWith(12)
    expect(dispatchMock).toHaveBeenCalledWith({
      type: 'repos/fetchRepoDetails',
      payload: 12,
    })
    expect(screen.getByText('graph-review-engine')).toBeInTheDocument()
    expect(screen.getByText('Repository automation')).toBeInTheDocument()
    expect(screen.getByText('Pull Requests')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('31')).toBeInTheDocument()
    expect(screen.getByText('93%')).toBeInTheDocument()
    expect(screen.getByText('Ada')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /settings/i })).toHaveAttribute(
      'href',
      '/repos/12/settings',
    )
  })

  it('renders loading, failed, and not-found states', () => {
    selectorState.repos = {
      currentRepo: null,
      status: 'loading',
      error: null,
    }

    const { rerender } = render(
      <MemoryRouter>
        <RepoOverview />
      </MemoryRouter>,
    )

    expect(screen.getByText(/Loading repository details/i)).toBeInTheDocument()

    selectorState.repos = {
      currentRepo: null,
      status: 'failed',
      error: 'Bad gateway',
    }

    rerender(
      <MemoryRouter>
        <RepoOverview />
      </MemoryRouter>,
    )

    expect(screen.getByText('Error Loading Repository')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(fetchRepoDetailsActionMock).toHaveBeenLastCalledWith(12)

    selectorState.repos = {
      currentRepo: null,
      status: 'succeeded',
      error: null,
    }

    rerender(
      <MemoryRouter>
        <RepoOverview />
      </MemoryRouter>,
    )

    expect(screen.getByText('Repository not found')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /view all repositories/i }))
    expect(navigateMock).toHaveBeenCalledWith('/repositories')
  })
})
