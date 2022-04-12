import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PullRequests from '../index'

const dispatchMock = vi.fn()
const fetchPullRequestsActionMock = vi.fn((repoId: number) => ({
  type: 'pullRequests/fetchList',
  payload: repoId,
}))
const getReviewHistoryMock = vi.fn()
const selectorState = {
  pullRequests: {
    pullRequests: {} as Record<number, any[]>,
    currentPR: null as any,
    status: 'idle',
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/PullRequestAction', () => ({
  fetchPullRequestsAction: (repoId: number) => fetchPullRequestsActionMock(repoId),
}))

vi.mock('../../../api/CodeReviewAPi', () => ({
  getReviewHistory: (...args: any[]) => getReviewHistoryMock(...args),
}))

vi.mock('react-redux', async () => {
  const actual = await vi.importActual<any>('react-redux')
  return {
    ...actual,
    useDispatch: () => dispatchMock,
    useSelector: (fn: any) => fn(selectorState),
  }
})

function renderPullRequestsPage() {
  return render(
    <MemoryRouter initialEntries={['/repos/7/pulls']}>
      <Routes>
        <Route path="/repos/:repoId/pulls" element={<PullRequests />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PullRequests page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    fetchPullRequestsActionMock.mockClear()
    getReviewHistoryMock.mockReset()
    selectorState.pullRequests = {
      pullRequests: {},
      currentPR: null,
      status: 'idle',
      error: null,
    }
  })

  it('loads pull requests, resolves workflow history, and filters the list', async () => {
    selectorState.pullRequests = {
      pullRequests: {
        7: [
          {
            id: 11,
            number: 22,
            title: 'Improve review orchestration',
            status: 'open',
            author: { name: 'Ada', avatarUrl: '/ada.png' },
            createdAt: '2026-05-18T10:00:00.000Z',
          },
          {
            id: 12,
            number: 23,
            title: 'Fix graph cache invalidation',
            status: 'closed',
            author: { name: 'Linus', avatarUrl: '/linus.png' },
            createdAt: '2026-05-17T10:00:00.000Z',
          },
        ],
      },
      currentPR: null,
      status: 'succeeded',
      error: null,
    }
    getReviewHistoryMock.mockImplementation(async (_context, prId) => {
      if (prId === 11) {
        return [
          { id: 100, status: 'completed' },
          { id: 101, status: 'completed' },
        ]
      }
      throw new Error('history unavailable')
    })

    renderPullRequestsPage()

    expect(fetchPullRequestsActionMock).toHaveBeenCalledWith(7)
    expect(screen.getByText('Improve review orchestration')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Completed')).toBeInTheDocument()
      expect(screen.getByText('Unavailable')).toBeInTheDocument()
    })
    expect(getReviewHistoryMock).toHaveBeenCalledTimes(2)

    fireEvent.change(screen.getByPlaceholderText(/search pull requests/i), {
      target: { value: 'graph' },
    })
    expect(screen.queryByText('Improve review orchestration')).not.toBeInTheDocument()
    expect(screen.getByText('Fix graph cache invalidation')).toBeInTheDocument()
