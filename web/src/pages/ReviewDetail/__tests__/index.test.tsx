import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PullRequestDetail from '../index'

const dispatchMock = vi.fn()
const fetchPRDetailsActionMock = vi.fn((payload: { repoId: number; prNumber: number }) => ({
  type: 'pullRequests/fetchDetail',
  payload,
}))
const getReviewHistoryMock = vi.fn()
const selectorState = {
  pullRequests: {
    currentPR: null as any,
    pullRequests: {},
    status: 'idle',
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/PullRequestAction', () => ({
  fetchPRDetailsAction: (payload: { repoId: number; prNumber: number }) =>
    fetchPRDetailsActionMock(payload),
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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ repoId: '8', prNumber: '42' }),
  }
})

describe('PullRequestDetail page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    fetchPRDetailsActionMock.mockClear()
    getReviewHistoryMock.mockReset()
    selectorState.pullRequests = {
      currentPR: null,
      pullRequests: {},
      status: 'idle',
      error: null,
    }
  })

  it('renders PR details, workflow history, diffs, reviews, and comments', async () => {
    selectorState.pullRequests = {
      pullRequests: {},
      status: 'succeeded',
      error: null,
      currentPR: {
        id: 310,
        number: 42,
        state: 'open',
        title: 'Stabilize PR review pipeline',
        body: 'This PR wires the backend review workflow.',
        created_at: '2026-05-18T10:00:00.000Z',
        user: { login: 'octocat', avatar_url: '/octo.png' },
        files: [
          {
            id: 1,
            filename: 'src/main.ts',
            additions: 14,
            deletions: 2,
            patch: '@@ -1,1 +1,2 @@\n+console.log("ok");',
          },
        ],
        reviews: [
          {
            id: 91,
            state: 'APPROVED',
            body: 'Looks good to me.',
            submitted_at: '2026-05-18T12:00:00.000Z',
            user: { login: 'reviewer', avatar_url: '/rev.png' },
          },
        ],
        comments: [
          {
            id: 51,
            body: 'Please add one more test.',
            created_at: '2026-05-18T13:00:00.000Z',
            path: 'src/main.ts',
            line: 44,
            user: { login: 'commenter', avatar_url: '/c.png' },
          },
        ],
      },
    }
    getReviewHistoryMock.mockResolvedValue([
      {
        id: 501,
        status: 'completed',
        createdAt: '2026-05-18T10:00:00.000Z',
        updatedAt: '2026-05-18T11:00:00.000Z',
        threadCount: 2,
        hasReviewData: true,
        errorMessage: null,
      },
    ])

    render(
      <MemoryRouter>
        <PullRequestDetail />
      </MemoryRouter>,
    )

    expect(fetchPRDetailsActionMock).toHaveBeenCalledWith({ repoId: 8, prNumber: 42 })
    await waitFor(() => {
      expect(getReviewHistoryMock).toHaveBeenCalledWith('pr', 310)
    })

    expect(screen.getByText('Stabilize PR review pipeline')).toBeInTheDocument()
    expect(screen.getByText(/this pr wires the backend review workflow/i)).toBeInTheDocument()
    expect(screen.getByText('octocat')).toBeInTheDocument()
    expect(screen.getByText('Files Changed')).toBeInTheDocument()
    expect(screen.getByText('Approved')).toBeInTheDocument()
    expect(screen.getByText('Please add one more test.')).toBeInTheDocument()
    expect(screen.getByText('Line 44')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open review/i })).toHaveAttribute(
      'href',
      '/commit-review/501',
    )

    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/console\.log\("ok"\)/i)).toBeInTheDocument()
  })
