import { act, renderHook } from '@testing-library/react'
import React from 'react'
import { describe, expect, it } from 'vitest'
import { SidebarProvider, useSidebar } from '../SidebarContext'

describe('SidebarContext', () => {
  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useSidebar())).toThrow('useSidebar must be used within a SidebarProvider')
  })

  it('provides open state and setter', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SidebarProvider>{children}</SidebarProvider>
    )
    const { result } = renderHook(() => useSidebar(), { wrapper })

    expect(result.current.isOpen).toBe(true)
    act(() => {
      result.current.setIsOpen(false)
    })
    expect(result.current.isOpen).toBe(false)
  })
})
