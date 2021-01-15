import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const dispatchMock = vi.fn()
const selectorState = {
  auth: { token: null },
}

vi.mock('./redux/store', () => ({
  default: {},
  RootState: {},
}))

vi.mock('./redux/slices/AuthSlice', () => ({
  restoreAuth: () => ({ type: 'auth/restoreAuth' }),
}))

vi.mock('react-redux', async () => {
  const actual = await vi.importActual<any>('react-redux')
  return {
    ...actual,
    useDispatch: () => dispatchMock,
    useSelector: (fn: any) => fn(selectorState),
  }
})

vi.mock('./contexts/SidebarContext', () => ({
  SidebarProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useSidebar: () => ({ isOpen: true }),
}))

vi.mock('./components/Sidebar', () => ({
  default: () => <div>Sidebar</div>,
}))

vi.mock('./pages/Dashboard', () => ({ default: () => <div>Dashboard Page</div> }))
vi.mock('./pages/Repositories', () => ({ default: () => <div>Repositories Page</div> }))
vi.mock('./pages/RepoRegistration', () => ({ default: () => <div>Repo Registration Page</div> }))
vi.mock('./pages/Login/index', () => ({ default: () => <div>Login Page</div> }))
vi.mock('./pages/RepoOverview', () => ({ default: () => <div>Repo Overview Page</div> }))
vi.mock('./pages/RepoSettings', () => ({ default: () => <div>Repo Settings Page</div> }))
vi.mock('./pages/Reviews', () => ({ default: () => <div>Pull Requests Page</div> }))
vi.mock('./pages/ReviewDetail', () => ({ default: () => <div>Pull Request Detail Page</div> }))
vi.mock('./pages/CodeReview/code-review', () => ({ default: () => <div>Code Review Page</div> }))
vi.mock('./pages/CodeReview/commit-detail', () => ({ default: () => <div>Commit Detail Page</div> }))
vi.mock('./pages/CodeReview/commit-list', () => ({ default: () => <div>Commit List Page</div> }))

import App from './App'

describe('App routes', () => {
  beforeEach(() => {
    dispatchMock.mockClear()
    selectorState.auth.token = null
    window.history.pushState({}, '', '/')
  })

  afterEach(() => {
    cleanup()
  })

  it('renders login route and restores auth on startup', async () => {
    render(<App />)

    expect(screen.getByText('Login Page')).toBeInTheDocument()
    await waitFor(() => {
      expect(dispatchMock).toHaveBeenCalledWith({ type: 'auth/restoreAuth' })
    })
  })

  it('renders protected route content when token exists', async () => {
    selectorState.auth.token = 'jwt'
    window.history.pushState({}, '', '/dashboard')

    render(<App />)

    expect(screen.getAllByText('Sidebar').length).toBeGreaterThan(0)
    expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
  })
})
