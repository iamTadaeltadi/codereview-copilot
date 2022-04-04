import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Repositories from '../index'

const dispatchMock = vi.fn()
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

describe('Repositories page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    fetchReposMock.mockClear()
    selectorState.repos = {
      repos: [],
      status: 'idle',
      error: null,
    }
  })

  it('dispatches fetch on idle and renders repository rows with filtering', () => {
    selectorState.repos = {
      repos: [
        { id: 1, name: 'alpha-service', description: 'Main API', language: 'TypeScript', stars: 4 },
        { id: 2, name: 'beta-worker', description: '', language: '', stars: undefined },
      ],
      status: 'idle',
      error: null,
    }

    render(
      <MemoryRouter>
        <Repositories />
      </MemoryRouter>,
    )

    expect(fetchReposMock).toHaveBeenCalledTimes(1)
    expect(dispatchMock).toHaveBeenCalledWith({ type: 'repos/fetchRepos' })
    expect(screen.getByText('alpha-service')).toBeInTheDocument()
    expect(screen.getByText('beta-worker')).toBeInTheDocument()
    expect(screen.getByText('No description provided')).toBeInTheDocument()
    expect(screen.getByText('TypeScript')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /add repository/i })).toHaveAttribute(
      'href',
      '/repo-registration',
    )

    fireEvent.change(screen.getByPlaceholderText(/search repositories/i), {
      target: { value: 'beta' },
    })

    expect(screen.queryByText('alpha-service')).not.toBeInTheDocument()
    expect(screen.getByText('beta-worker')).toBeInTheDocument()
  })

  it('renders loading, failure, and empty states', () => {
    selectorState.repos = {
      repos: [],
      status: 'loading',
      error: null,
    }

    const { rerender } = render(
      <MemoryRouter>
        <Repositories />
      </MemoryRouter>,
    )

    expect(document.querySelector('.animate-spin')).toBeTruthy()

    selectorState.repos = {
      repos: [],
      status: 'failed',
      error: 'Network down',
    }

    rerender(
      <MemoryRouter>
        <Repositories />
      </MemoryRouter>,
    )

    expect(screen.getByText('Error occurred')).toBeInTheDocument()
    expect(screen.getByText('Network down')).toBeInTheDocument()

    selectorState.repos = {
      repos: [],
      status: 'succeeded',
      error: null,
    }

    rerender(
      <MemoryRouter>
        <Repositories />
      </MemoryRouter>,
    )

    expect(screen.getByText('No repositories found')).toBeInTheDocument()
    expect(screen.getByText(/Try adjusting your search term/i)).toBeInTheDocument()
  })
})
