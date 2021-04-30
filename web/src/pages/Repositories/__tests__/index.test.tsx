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
