import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LoginForm from '../login-form'
import LoginPage from '../../index'
import FormCheckbox from '../form-checkbox'
import FormInput from '../form-input'
import SocialLoginButtons from '../social-login-buttons'
import SubmitButton from '../submit-button'

const loginThunkMock = vi.fn()
const dispatchMock = vi.fn()

vi.mock('../../../../redux/actions/AuthAction', () => ({
  loginUser: (...args: any[]) => loginThunkMock(...args),
}))

vi.mock('../../../../api/AuthApi', () => ({
  getGitHubLoginUrl: () => 'https://github.com/login/oauth',
}))

vi.mock('react-redux', async () => {
  const actual = await vi.importActual<any>('react-redux')
  return {
    ...actual,
    useDispatch: () => dispatchMock,
  }
})

describe('login ui modules', () => {
  beforeEach(() => {
    loginThunkMock.mockReset()
    dispatchMock.mockReset()
    dispatchMock.mockResolvedValue({ type: 'auth/loginUser/fulfilled' })
    loginThunkMock.mockReturnValue({ type: 'auth/loginUser' })
  })

  it('login form submits credentials and toggles loading state', async () => {
    render(
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'dev@example.com' } })
    fireEvent.change(screen.getByPlaceholderText('••••••••••••'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in with email/i }))

    await waitFor(() => {
      expect(loginThunkMock).toHaveBeenCalledWith({
        email: 'dev@example.com',
        password: 'secret',
      })
      expect(dispatchMock).toHaveBeenCalled()
    })
  })

  it('login page and smaller controls render expected content', () => {
    const inputChange = vi.fn()
    render(
      <MemoryRouter>
      <>
        <LoginPage />
        <FormCheckbox id="remember" label="Remember me" required />
        <FormInput id="password" type="password" value="" onChange={inputChange} />
        <SocialLoginButtons />
        <SubmitButton text="Send" isLoading />
      </>
      </MemoryRouter>,
    )

    expect(screen.getByText('AI Review Workspace')).toBeInTheDocument()
    expect(screen.getByText(/New users should start with GitHub OAuth/i)).toBeInTheDocument()
    const githubLinks = screen.getAllByRole('link', { name: /continue with github/i })
    expect(githubLinks).toHaveLength(2)
    expect(githubLinks[0]).toHaveAttribute('href', 'https://github.com/login/oauth')
    expect(screen.getAllByText('Remember me')[0]).toBeInTheDocument()

    expect(document.getElementById('password')).toHaveAttribute('type', 'password')
  })
})
