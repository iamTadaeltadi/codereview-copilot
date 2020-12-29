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
