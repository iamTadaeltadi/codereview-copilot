import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RepoSettingsPage from '../index'

const dispatchMock = vi.fn()
const unwrapMock = vi.fn().mockResolvedValue(undefined)
const fetchRepoDetailsActionMock = vi.fn((repoId: number) => ({
  type: 'repos/fetchDetails',
  payload: repoId,
}))
const updateRepoSettingsActionMock = vi.fn((payload: any) => ({
  type: 'repos/updateSettings',
  payload,
}))
const selectorState = {
  repos: {
    currentRepo: null as any,
    status: 'idle',
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/RepoAction', () => ({
  fetchRepoDetailsAction: (repoId: number) => fetchRepoDetailsActionMock(repoId),
  updateRepoSettingsAction: (payload: any) => updateRepoSettingsActionMock(payload),
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
    useParams: () => ({ repoId: '12' }),
  }
})

describe('RepoSettings page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    dispatchMock.mockImplementation((action: any) => {
      if (action?.type === 'repos/updateSettings') {
        return { unwrap: unwrapMock }
      }
      return action
    })
    unwrapMock.mockClear()
    fetchRepoDetailsActionMock.mockClear()
    updateRepoSettingsActionMock.mockClear()
    selectorState.repos = {
      currentRepo: null,
      status: 'idle',
      error: null,
    }
  })

  it('populates editable fields and submits parsed settings to the backend action', async () => {
    selectorState.repos = {
      status: 'succeeded',
      error: null,
      currentRepo: {
        id: 12,
