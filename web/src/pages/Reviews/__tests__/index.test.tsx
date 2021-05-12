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
