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
