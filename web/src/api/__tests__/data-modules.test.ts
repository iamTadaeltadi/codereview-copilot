import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = {
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}

vi.mock('../client', () => ({
  apiClient: client,
  buildAbsoluteUrl: (path: string) => `http://localhost:8000${path}`,
}))

vi.mock('../../constants/review-report-response', () => ({
  reviewReport: {
    review: { syntax: [], standards: [], error_analysis: [], final: [] },
    status: 'completed',
    artifacts: { fixes: [], summary: 'fallback' },
  },
}))

describe('frontend data api modules', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('normalizes commit list and commit detail responses', async () => {
    const module = await import('../CommitsApi')
    client.get
      .mockResolvedValueOnce({
        data: [
          {
            id: 1,
            commit_hash: 'abcdef',
            author_name: 'Alice',
            message: 'Fix bug',
            committer_name: 'Bob',
            committed_date: '2026-05-20T00:00:00Z',
          },
        ],
      })
      .mockResolvedValueOnce({
        data: {
          id: 2,
          commit_hash: '1234567890abcdef',
          author_github_id: 'alice-gh',
          message: 'Add tests',
          committer_github_id: 'ci-bot',
          timestamp: '2026-05-19T00:00:00Z',
          url: 'https://github.com/demo/commit/123',
          repository: { id: 9, repo_name: 'owner/repo' },
          reviews: [{ id: 1 }, { id: 2 }],
        },
      })

    const commits = await module.getCommits(5)
    const detail = await module.getCommitDetail('1234567890abcdef')

    expect(commits[0]).toMatchObject({
      commitHash: 'abcdef',
      author: 'Alice',
      reviewer: 'Bob',
      changes: 'View',
    })
    expect(detail.repositoryName).toBe('owner/repo')
    expect(detail.reviewCount).toBe(2)
  })

  it('normalizes pull request list and detail responses', async () => {
    const module = await import('../PullRequestApi')
    client.get
      .mockResolvedValueOnce({
        data: [
          {
            id: 11,
            pr_number: 7,
            title: 'Refactor auth',
            status: 'open',
            created_at_gh: '2026-05-18T00:00:00Z',
            user_login: 'octocat',
            user_avatar_url: 'avatar.png',
          },
        ],
      })
      .mockResolvedValueOnce({
        data: {
          id: 12,
          pr_number: 9,
          title: 'Merge feature',
          status: 'closed',
          merged_at_gh: '2026-05-19T00:00:00Z',
          user_login: 'octocat',
          head_sha: 'abc123',
          base_sha: 'def456',
        },
      })

    const prs = await module.fetchPullRequests(3)
    const detail = await module.fetchPRDetails(3, 9)

    expect(prs[0]).toMatchObject({
      repoId: 3,
      number: 7,
      author: { name: 'octocat', avatarUrl: 'avatar.png' },
    })
    expect(detail.status).toBe('merged')
    expect(detail.head.sha).toBe('abc123')
  })

  it('normalizes repository list, detail, creation and settings updates', async () => {
    const module = await import('../ReposApi')
    const repoPayload = {
      id: 21,
      repo_name: 'owner/repo',
      repo_url: 'https://github.com/owner/repo',
      description: 'Demo repo',
      coding_standards: ['DRY'],
      code_metrics: ['complexity'],
      llm_preference: 'gpt-4o',
      webhook_url: 'https://hook.example',
      webhook_last_event_at: '2026-05-20T00:00:00Z',
      owner: { is_admin: true },
    }
    client.get
      .mockResolvedValueOnce({ data: [repoPayload] })
      .mockResolvedValueOnce({ data: repoPayload })
      .mockResolvedValueOnce({ data: repoPayload })
    client.post.mockResolvedValueOnce({ data: repoPayload })
