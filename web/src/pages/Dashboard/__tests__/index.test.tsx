import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from '../index'

const dispatchMock = vi.fn()
const navigateMock = vi.fn()
const fetchReposMock = vi.fn(() => ({ type: 'repos/fetchRepos' }))
const selectorState = {
  repos: {
    repos: [] as any[],
    status: 'idle',
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/RepoAction', () => ({
  fetchRepos: () => fetchReposMock(),
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

describe('Dashboard page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    navigateMock.mockReset()
    fetchReposMock.mockClear()
    selectorState.repos = {
      repos: [],
      status: 'idle',
      error: null,
    }
  })

  it('renders repository cards and navigates to repo pages', () => {
    selectorState.repos = {
      repos: [
        {
          id: 11,
          name: 'alpha-review',
          repoUrl: 'https://github.com/org/alpha-review',
          description: 'Alpha',
          webhookStatus: true,
        },
        {
          id: 12,
          name: 'beta-review',
          repoUrl: '',
          description: '',
          webhookStatus: false,
        },
      ],
      status: 'idle',
      error: null,
    }

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(fetchReposMock).toHaveBeenCalledTimes(1)
    expect(screen.getByText('alpha-review')).toBeInTheDocument()
    expect(screen.getByText('beta-review')).toBeInTheDocument()
    expect(screen.getByText('Configured')).toBeInTheDocument()
    expect(screen.getByText('Pending')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText(/search repositories/i), {
      target: { value: 'beta' },
    })

    expect(screen.queryByText('alpha-review')).not.toBeInTheDocument()
    expect(screen.getByText('beta-review')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /add repository/i }))
    expect(navigateMock).toHaveBeenCalledWith('/repo-registration')

    fireEvent.click(screen.getByRole('button', { name: /beta-review/i }))
    expect(navigateMock).toHaveBeenCalledWith('/repos/12')

    fireEvent.click(screen.getByRole('button', { name: /settings/i }))
    expect(navigateMock).toHaveBeenCalledWith('/repos/12/settings')
  })

  it('renders loading, failed, and empty states', () => {
    selectorState.repos = {
      repos: [],
      status: 'loading',
      error: null,
    }

    const { rerender } = render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(screen.getByText(/Loading repositories/i)).toBeInTheDocument()

    selectorState.repos = {
      repos: [],
      status: 'failed',
      error: 'API unavailable',
    }

    rerender(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(screen.getByText('Error Loading Data')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(dispatchMock).toHaveBeenCalledWith({ type: 'repos/fetchRepos' })

    selectorState.repos = {
      repos: [],
      status: 'succeeded',
      error: null,
    }

    rerender(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(screen.getByText('No repositories found')).toBeInTheDocument()
  })
})
