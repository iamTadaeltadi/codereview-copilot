import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CommitDetail from '../commit-detail'

const dispatchMock = vi.fn()
const fetchCommitDetailMock = vi.fn((commitHash: string) => ({
  type: 'commitDetail/fetch',
  payload: commitHash,
}))
const getReviewHistoryMock = vi.fn()
const selectorState = {
  commitDetail: {
    detail: null as any,
    loading: false,
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/CommitDetailAction', () => ({
  fetchCommitDetail: (commitHash: string) => fetchCommitDetailMock(commitHash),
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
    useParams: () => ({ id: 'abc123' }),
  }
})

describe('CommitDetail page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    fetchCommitDetailMock.mockClear()
    getReviewHistoryMock.mockReset()
    selectorState.commitDetail = {
      detail: null,
      loading: false,
      error: null,
    }
  })

  it('renders commit detail data, review history, and diff rows', async () => {
    selectorState.commitDetail = {
      loading: false,
      error: null,
      detail: {
        message: 'Normalize commit reporting',
        commitHash: 'abc123',
        author: 'Ada',
        date: '2026-05-18T10:00:00.000Z',
        repositoryId: 7,
        repositoryName: 'graph-review-engine',
        changes: 14,
        reviewer: 'Linus',
        description: 'More consistent review output',
        diff: 'https://example.com/diff',
        diffBlocks: [
          { type: 'addition', oldLine: null, newLine: 10, content: '+ const ready = true;' },
          { type: 'deletion', oldLine: 11, newLine: null, content: '- const ready = false;' },
        ],
      },
    }
    getReviewHistoryMock.mockResolvedValue([
      {
        id: 401,
        status: 'completed',
        createdAt: '2026-05-18T10:00:00.000Z',
        threadCount: 1,
        hasReviewData: true,
        errorMessage: null,
      },
    ])

    render(
      <MemoryRouter>
        <CommitDetail />
      </MemoryRouter>,
    )

    expect(fetchCommitDetailMock).toHaveBeenCalledWith('abc123')
    await waitFor(() => {
      expect(getReviewHistoryMock).toHaveBeenCalledWith('commit', 'abc123')
    })

    expect(screen.getByText('Normalize commit reporting')).toBeInTheDocument()
    expect(screen.getByText('graph-review-engine')).toBeInTheDocument()
    expect(screen.getByText('Open review')).toHaveAttribute('href', '/commit-review/401')
    expect(screen.getByText('+ const ready = true;')).toBeInTheDocument()
    expect(screen.getByText('- const ready = false;')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /view repository/i })).toHaveAttribute(
      'href',
      '/repos/7',
    )
  })

  it('renders loading, error, missing-detail, and history-error states', async () => {
    selectorState.commitDetail = {
      detail: null,
      loading: true,
      error: null,
    }

    const { rerender } = render(
      <MemoryRouter>
        <CommitDetail />
      </MemoryRouter>,
    )

    expect(screen.getByText(/loading commit details/i)).toBeInTheDocument()

    selectorState.commitDetail = {
      detail: null,
      loading: false,
      error: 'Could not load commit',
    }

    rerender(
      <MemoryRouter>
        <CommitDetail />
      </MemoryRouter>,
    )

    expect(screen.getByText(/error: could not load commit/i)).toBeInTheDocument()

    selectorState.commitDetail = {
      detail: null,
      loading: false,
      error: null,
    }

    rerender(
      <MemoryRouter>
        <CommitDetail />
      </MemoryRouter>,
    )

    expect(screen.getByText(/no commit details found/i)).toBeInTheDocument()

    selectorState.commitDetail = {
      loading: false,
      error: null,
      detail: {
        message: 'Fallback commit',
        commitHash: 'abc123',
        author: 'Ada',
        date: '2026-05-18T10:00:00.000Z',
        repositoryId: null,
        repositoryName: '',
        changes: 0,
        reviewer: '',
        description: '',
        diff: '',
        diffBlocks: [],
      },
    }
    getReviewHistoryMock.mockRejectedValue(new Error('history failed'))

    rerender(
      <MemoryRouter>
        <CommitDetail />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('history failed')).toBeInTheDocument()
    })
    expect(
      screen.getByText(/structured diff blocks are not available in the current backend response/i),
    ).toBeInTheDocument()
  })
})
