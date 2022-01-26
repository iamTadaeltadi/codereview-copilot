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

    await import('../client')

    localStorage.setItem('authUser', '{bad-json')
    const config = getRequestInterceptor()({})
    expect(config.headers).toBeUndefined()
    expect(localStorage.getItem('authUser')).toBeNull()
  })

  it('login exchanges credentials for token and normalized current user', async () => {
    const { client } = createMocks()
    client.post.mockResolvedValue({ data: { access: 'jwt-token' } })
    client.get.mockResolvedValue({
      data: {
        id: 7,
        username: '',
        email: 'dev@example.com',
        is_admin: 1,
        github_id: '42',
      },
    })

    vi.doMock('axios', () => ({
      default: {
        create: vi.fn(() => client),
      },
    }))

    const authModule = await import('../AuthApi')
    const result = await authModule.login({
      email: 'dev@example.com',
      password: 'secret',
    })

    expect(client.post).toHaveBeenCalledWith('/auth/token/', {
      username: 'dev@example.com',
      password: 'secret',
    })
    expect(client.get).toHaveBeenCalledWith('/user/', {
      headers: { Authorization: 'Bearer jwt-token' },
    })
    expect(result).toEqual({
      token: 'jwt-token',
      user: {
        id: 7,
        username: 'dev@example.com',
        email: 'dev@example.com',
        isAdmin: true,
        githubId: '42',
      },
    })
    expect(authModule.getGitHubLoginUrl()).toBe('https://api.example.com/api/v1/auth/github/login/')
  })
})
