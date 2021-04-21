import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RepoRegistration from '../index'

const dispatchMock = vi.fn()
const navigateMock = vi.fn()
const createRepositoryActionMock = vi.fn((payload: any) => ({
  type: 'repos/createRepository',
  payload,
}))
const selectorState = {
  repos: {
    status: 'idle',
    error: null as string | null,
  },
}

vi.mock('../../../redux/actions/RepoAction', () => ({
  createRepositoryAction: (payload: any) => createRepositoryActionMock(payload),
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
    useNavigate: () => navigateMock,
  }
})

describe('RepoRegistration page', () => {
  beforeEach(() => {
    dispatchMock.mockReset()
    navigateMock.mockReset()
    createRepositoryActionMock.mockClear()
    selectorState.repos = {
      status: 'idle',
      error: null,
    }
  })

  it('parses preview values and submits repository creation payload', async () => {
    dispatchMock.mockReturnValue({
      unwrap: () => Promise.resolve({ id: 42 }),
    })

    render(
      <MemoryRouter>
        <RepoRegistration />
