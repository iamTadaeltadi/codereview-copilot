import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SidebarProvider } from '../../contexts/SidebarContext'
import Sidebar from '../Sidebar'

const dispatchMock = vi.fn()
const navigateMock = vi.fn()
const locationMock = { pathname: '/dashboard' }

vi.mock('react-redux', async () => {
  const actual = await vi.importActual<any>('react-redux')
  return {
    ...actual,
    useDispatch: () => dispatchMock,
  }
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useLocation: () => locationMock,
  }
})

describe('Sidebar', () => {
  beforeEach(() => {
    dispatchMock.mockClear()
    navigateMock.mockClear()
    localStorage.clear()
  })

  it('renders links, toggles sidebar, and logs out', () => {
    render(
      <MemoryRouter>
        <SidebarProvider>
          <Sidebar />
        </SidebarProvider>
      </MemoryRouter>,
    )

    expect(screen.getByText('Code Review AI')).toBeInTheDocument()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /logout/i }))
    expect(dispatchMock).toHaveBeenCalled()
    expect(navigateMock).toHaveBeenCalledWith('/')

    fireEvent.click(screen.getAllByRole('button')[0])
    expect(screen.queryByText('Code Review AI')).not.toBeInTheDocument()
  })
})
