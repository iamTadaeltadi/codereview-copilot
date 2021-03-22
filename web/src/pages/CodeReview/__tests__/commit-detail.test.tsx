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
