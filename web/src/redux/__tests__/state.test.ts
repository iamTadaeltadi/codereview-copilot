import { beforeEach, describe, expect, it, vi } from 'vitest'

const authLoginMock = vi.fn()
const repoApiMock = {
  fetchReposFromApi: vi.fn(),
  fetchRepoDetails: vi.fn(),
  createRepository: vi.fn(),
  fetchRepoSettings: vi.fn(),
  updateRepoSettings: vi.fn(),
}
const prApiMock = {
  fetchPullRequests: vi.fn(),
  fetchPRDetails: vi.fn(),
}
const commitApiMock = {
  getCommits: vi.fn(),
  getCommitDetail: vi.fn(),
}
const codeReviewApiMock = {
  getCodeReview: vi.fn(),
}

vi.mock('../../api/AuthApi', () => ({ login: authLoginMock }))
vi.mock('../../api/ReposApi', () => repoApiMock)
vi.mock('../../api/PullRequestApi', () => prApiMock)
vi.mock('../../api/CommitsApi', () => commitApiMock)
vi.mock('../../api/CodeReviewAPi', () => codeReviewApiMock)

describe('redux state modules', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('auth slice reducers and login thunk update state correctly', async () => {
    const authSlice = await import('../slices/AuthSlice')
    const { loginUser } = await import('../actions/AuthAction')

    const restored = authSlice.default(
      undefined,
      authSlice.restoreAuth(),
    )
    expect(restored.token).toBeNull()

    localStorage.setItem('authUser', JSON.stringify({ user: { id: 1 }, token: 'jwt' }))
    const withAuth = authSlice.default(undefined, authSlice.restoreAuth())
    expect(withAuth.token).toBe('jwt')

    localStorage.setItem('authUser', '{broken')
    const broken = authSlice.default(undefined, authSlice.restoreAuth())
    expect(broken.token).toBeNull()

    const loggedOut = authSlice.default(withAuth, authSlice.logout())
    expect(loggedOut.token).toBeNull()

    authLoginMock.mockResolvedValue({ user: { id: 1, username: 'dev' }, token: 'jwt' })
    const thunkResult = await loginUser({ email: 'dev@example.com', password: 'secret' })(vi.fn(), () => ({}), undefined)
    expect(thunkResult.payload).toEqual({ user: { id: 1, username: 'dev' }, token: 'jwt' })

    const pending = authSlice.default(undefined, loginUser.pending('1', { email: 'a', password: 'b' }))
    const fulfilled = authSlice.default(pending, loginUser.fulfilled({ user: { id: 1 }, token: 'jwt' }, '1', { email: 'a', password: 'b' }))
    const rejected = authSlice.default(pending, loginUser.rejected(new Error('bad creds'), '1', { email: 'a', password: 'b' }))
    expect(fulfilled.token).toBe('jwt')
    expect(rejected.error).toBe('bad creds')
  })

  it('repo slice and repo actions cover success and failure flows', async () => {
    const repoSlice = await import('../slices/RepoSlice')
    const actions = await import('../actions/RepoAction')

    repoApiMock.fetchReposFromApi.mockResolvedValue([{ id: 1, name: 'repo-a' }])
    const fetchReposResult = await actions.fetchRepos()(vi.fn(), () => ({}), undefined)
    expect(fetchReposResult.payload).toEqual([{ id: 1, name: 'repo-a' }])

    let state = repoSlice.default(undefined, actions.fetchRepos.pending('1'))
    expect(state.status).toBe('loading')
    state = repoSlice.default(state, actions.fetchRepos.fulfilled([{ id: 1, name: 'repo-a' }], '1', undefined))
    expect(state.repos).toHaveLength(1)

