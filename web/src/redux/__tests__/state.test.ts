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

    state = repoSlice.default(state, actions.fetchRepoDetailsAction.fulfilled({ id: 1, name: 'repo-a' }, '2', 1))
    expect(state.currentRepo?.name).toBe('repo-a')

    state = repoSlice.default(
      { ...state, currentRepo: { id: 1, settings: {} } },
      actions.fetchRepoSettingsAction.fulfilled({ repoId: 1, settings: { llmModel: 'gpt-4' } }, '3', 1),
    )
    expect(state.currentRepo.settings.llmModel).toBe('gpt-4')

    state = repoSlice.default(state, actions.createRepositoryAction.fulfilled({ id: 2, name: 'repo-b' }, '4', {} as any))
    expect(state.currentRepo?.name).toBe('repo-b')
    state = repoSlice.default(state, actions.updateRepoSettingsAction.fulfilled({ id: 2, name: 'repo-b', settings: { llmModel: 'gpt-4o' } }, '5', {} as any))
    expect(state.currentRepo?.settings.llmModel).toBe('gpt-4o')

    state = repoSlice.default(state, actions.fetchRepos.rejected(new Error('no repos'), '6'))
    expect(state.status).toBe('failed')
  })

  it('pull request, commit, commit detail and code review slices handle transitions', async () => {
    const prSlice = await import('../slices/PullRequestsSlice')
    const prActions = await import('../actions/PullRequestAction')
    const commitSlice = await import('../slices/CommitsSlice')
    const commitActions = await import('../actions/CommitAction')
    const commitDetailSlice = await import('../slices/CommitDetailSlice')
    const commitDetailActions = await import('../actions/CommitDetailAction')
    const reviewSlice = await import('../slices/CodeReviewSlice')
    const reviewApi = await import('../../api/CodeReviewAPi')

    let prState = prSlice.default(undefined, prActions.fetchPullRequestsAction.pending('1', 9))
    prState = prSlice.default(prState, prActions.fetchPullRequestsAction.fulfilled({ repoId: 9, pullRequests: [{ id: 1, number: 2 }] }, '1', 9))
    prState = prSlice.default(prState, prActions.fetchPRDetailsAction.fulfilled({ repoId: 9, prNumber: 2, prDetails: { id: 1, state: 'closed', merged_at: '2026-01-01' } as any }, '2', { repoId: 9, prNumber: 2 }))
    prState = prSlice.default(prState, prSlice.clearCurrentPR())
    expect(prState.pullRequests[9]).toHaveLength(1)
    expect(prState.currentPR).toBeNull()

    let commitState = commitSlice.default(undefined, commitActions.fetchCommits.pending('1', 9))
    commitState = commitSlice.default(commitState, commitActions.fetchCommits.fulfilled([{ id: 1, commitHash: 'abc' } as any], '1', 9))
    commitState = commitSlice.default(commitState, commitActions.fetchCommits.rejected(new Error('no commits'), '1', 9))
    expect(commitState.error).toBe('no commits')

    let detailState = commitDetailSlice.default(undefined, commitDetailActions.fetchCommitDetail.pending('1', 'abc'))
    detailState = commitDetailSlice.default(detailState, commitDetailActions.fetchCommitDetail.fulfilled({ id: 1, commitHash: 'abc' } as any, '1', 'abc'))
    detailState = commitDetailSlice.default(detailState, commitDetailActions.fetchCommitDetail.rejected(new Error('missing'), '1', 'abc'))
    expect(detailState.error).toBe('missing')

    let reviewState = reviewSlice.default(undefined, reviewSlice.fetchCodeReview.pending('1', 7))
    reviewState = reviewSlice.default(
      reviewState,
      reviewSlice.fetchCodeReview.fulfilled(
        {
          id: 7,
          chatThread: [],
          reviewRating: null,
          reviewFeedback: '',
        } as any,
        '1',
        7,
      ),
    )
    reviewState = reviewSlice.default(reviewState, reviewSlice.addChatMessage({ id: 1, text: 'hi' } as any))
    reviewState = reviewSlice.default(reviewState, reviewSlice.setReviewRating(9))
    reviewState = reviewSlice.default(reviewState, reviewSlice.setReviewFeedback('Looks good'))
    reviewState = reviewSlice.default(reviewState, reviewSlice.clearCodeReview())
    expect(reviewState.review).toBeNull()
    expect(typeof reviewApi.getCodeReview).toBe('function')
  })

  it('store exports reducers for all mounted slices', async () => {
    const storeModule = await import('../store')
    const state = storeModule.default.getState()
    expect(state).toHaveProperty('repos')
    expect(state).toHaveProperty('auth')
    expect(state).toHaveProperty('pullRequests')
    expect(state).toHaveProperty('commits')
    expect(state).toHaveProperty('commitDetail')
    expect(state).toHaveProperty('codeReview')
  })
})
