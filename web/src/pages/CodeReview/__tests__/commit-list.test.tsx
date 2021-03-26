import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CommitList from '../commit-list'

const dispatchMock = vi.fn()
const fetchCommitsMock = vi.fn((repoId: number) => ({
  type: 'commits/fetchList',
  payload: repoId,
}))
const getReviewHistoryMock = vi.fn()
const selectorState = {
  commits: {
    commits: [] as any[],
    loading: false,
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/CommitAction', () => ({
  fetchCommits: (repoId: number) => fetchCommitsMock(repoId),
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
    useParams: () => ({ id: '3' }),
  }
})

describe('CommitList page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    fetchCommitsMock.mockClear()
    getReviewHistoryMock.mockReset()
    selectorState.commits = {
      commits: [],
      loading: false,
      error: null,
    }
  })

  it('loads commits and annotates them with workflow status', async () => {
    selectorState.commits = {
      loading: false,
      error: null,
      commits: [
        {
          author: 'Ada',
          message: 'Improve parser',
          reviewer: 'Linus',
          commitHash: 'abc123',
