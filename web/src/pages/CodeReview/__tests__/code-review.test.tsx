import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CodeReviewPage from '../code-review'

const dispatchMock = vi.fn()
const fetchCodeReviewMock = vi.fn((id: number) => ({
  type: 'codeReview/fetch',
  payload: id,
}))
const clearCodeReviewMock = vi.fn(() => ({
  type: 'codeReview/clear',
}))
const createReviewThreadMock = vi.fn()
const replyToReviewThreadMock = vi.fn()
const selectorState = {
  codeReview: {
    review: null as any,
    loading: false,
    error: null as string | null,
  },
}

vi.mock('../../../redux/slices/CodeReviewSlice', () => ({
  fetchCodeReview: (id: number) => fetchCodeReviewMock(id),
  clearCodeReview: () => clearCodeReviewMock(),
}))

vi.mock('../../../api/CodeReviewAPi', () => ({
  createReviewThread: (...args: any[]) => createReviewThreadMock(...args),
  replyToReviewThread: (...args: any[]) => replyToReviewThreadMock(...args),
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
    useParams: () => ({ id: '77' }),
  }
})

describe('CodeReviewPage', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    dispatchMock.mockImplementation((action: any) => {
      if (action?.type === 'codeReview/fetch') {
        return { unwrap: vi.fn().mockResolvedValue(undefined) }
      }
      return action
    })
    fetchCodeReviewMock.mockClear()
    clearCodeReviewMock.mockClear()
    createReviewThreadMock.mockReset()
    replyToReviewThreadMock.mockReset()
    selectorState.codeReview = {
      review: null,
      loading: false,
      error: null,
    }
  })

  it('renders review data and sends feedback through a newly created thread', async () => {
    selectorState.codeReview = {
      loading: false,
      error: null,
      review: {
        id: 77,
        status: 'completed',
        contextLabel: 'PR #12 · Improve review UX',
        contextRoute: '/repos/2/pulls/12',
        threadCount: 0,
        errorMessage: null,
        activeThreadId: null,
        chatThread: [],
        raw: {
          review: {
            syntax: [{ issues: [{ file: 'src/app.ts', location: '12', description: 'Missing semicolon' }] }],
            standards: [{ issues: [{ file: 'src/app.ts', location: '15', standard: 'Prefer const' }] }],
            final: [
              {
                file: 'src/app.ts',
                summary: 'Core app module',
                ratings: {
                  'Code complexity': '8',
                  'Code duplication': '7',
                  'Code coverage': '9',
                },
                critical_issues: ['Missing tests'],
              },
            ],
          },
          status: 'completed',
          artifacts: {
            fixes: ['Use <strong>const</strong> instead of let'],
            summary: 'Summary',
          },
        },
      },
    }
    createReviewThreadMock.mockResolvedValue({ id: 901 })
    replyToReviewThreadMock.mockResolvedValue(undefined)

    const { unmount } = render(
      <MemoryRouter>
        <CodeReviewPage />
      </MemoryRouter>,
    )

    expect(fetchCodeReviewMock).toHaveBeenCalledWith(77)
    expect(screen.getByText('Review Workflow #77')).toBeInTheDocument()
    expect(screen.getByText('1 Critical Issues')).toBeInTheDocument()
    expect(screen.getByText('1 Standards Issues')).toBeInTheDocument()
    expect(screen.getByText('1 Suggested Fixes')).toBeInTheDocument()
    expect(screen.getByText('Missing semicolon')).toBeInTheDocument()
    expect(screen.getByText('Prefer const')).toBeInTheDocument()
    expect(screen.getByText('Missing tests')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to source item/i })).toHaveAttribute(
      'href',
      '/repos/2/pulls/12',
    )

    fireEvent.change(
      screen.getByPlaceholderText(/ask the review assistant to clarify/i),
      { target: { value: 'Can you explain the standards issue?' } },
    )
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => {
      expect(createReviewThreadMock).toHaveBeenCalledWith(77, 'Discussion for review 77')
    })
    expect(replyToReviewThreadMock).toHaveBeenCalledWith(
      901,
      'Can you explain the standards issue?',
    )
    expect(fetchCodeReviewMock).toHaveBeenCalledTimes(2)

    unmount()
    expect(clearCodeReviewMock).toHaveBeenCalledTimes(1)
  })

  it('renders loading, error, empty, and send-error states', async () => {
    selectorState.codeReview = {
      review: null,
      loading: true,
      error: null,
    }

    const { rerender } = render(
      <MemoryRouter>
        <CodeReviewPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    selectorState.codeReview = {
      review: null,
      loading: false,
      error: 'Review fetch failed',
    }

    rerender(
      <MemoryRouter>
        <CodeReviewPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('Review fetch failed')).toBeInTheDocument()

    selectorState.codeReview = {
      review: null,
      loading: false,
      error: null,
    }

    rerender(
      <MemoryRouter>
        <CodeReviewPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/no review data/i)).toBeInTheDocument()

    selectorState.codeReview = {
      loading: false,
      error: null,
      review: {
        id: 88,
        status: 'completed',
        contextLabel: 'Commit review',
        contextRoute: null,
        threadCount: 1,
        errorMessage: 'Partial pipeline failure',
        activeThreadId: 33,
        chatThread: [
          {
            id: 1,
            author: 'assistant',
            text: 'Initial note',
            isAI: true,
            timestamp: '2026-05-19T12:00:00.000Z',
          },
        ],
        raw: {
          review: { syntax: [], standards: [], final: [] },
          status: 'completed',
          artifacts: { fixes: [], summary: '' },
        },
      },
    }
    replyToReviewThreadMock.mockRejectedValue(new Error('reply failed'))

    rerender(
      <MemoryRouter>
        <CodeReviewPage />
      </MemoryRouter>,
    )

    fireEvent.change(
      screen.getByPlaceholderText(/ask the review assistant to clarify/i),
      { target: { value: 'Retry feedback' } },
    )
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => {
      expect(screen.getByText(/error sending message/i)).toBeInTheDocument()
    })
    expect(screen.getByText('reply failed')).toBeInTheDocument()
    expect(screen.getByText('Initial note')).toBeInTheDocument()
    expect(screen.getByText('Partial pipeline failure')).toBeInTheDocument()
  })
})
