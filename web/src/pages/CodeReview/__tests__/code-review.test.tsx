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
