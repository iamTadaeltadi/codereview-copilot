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
