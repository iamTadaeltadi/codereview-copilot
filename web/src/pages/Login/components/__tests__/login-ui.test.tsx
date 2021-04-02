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
