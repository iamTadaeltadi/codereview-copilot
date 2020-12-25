import { beforeEach, describe, expect, it, vi } from 'vitest'

const createMocks = () => {
  let requestInterceptor: ((config: any) => any) | undefined
  const client = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn((fn: (config: any) => any) => {
          requestInterceptor = fn
          return 1
        }),
      },
    },
  }

  return {
    client,
    getRequestInterceptor: () => requestInterceptor!,
  }
}

describe('client and auth api', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  it('buildAbsoluteUrl uses configured base url and request interceptor injects auth header', async () => {
    const { client, getRequestInterceptor } = createMocks()
    vi.doMock('axios', () => ({
      default: {
        create: vi.fn(() => client),
      },
    }))
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/')

    const clientModule = await import('../client')

    expect(clientModule.buildAbsoluteUrl('/auth/github')).toBe('https://api.example.com/auth/github')

    localStorage.setItem('authUser', JSON.stringify({ token: 'abc123' }))
    const config = getRequestInterceptor()({ headers: {} })
    expect(config.headers.Authorization).toBe('Bearer abc123')
  })

  it('request interceptor clears invalid stored auth payloads', async () => {
    const { client, getRequestInterceptor } = createMocks()
    vi.doMock('axios', () => ({
      default: {
        create: vi.fn(() => client),
      },
    }))
