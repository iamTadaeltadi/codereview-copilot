import { apiClient } from "./client";

export interface Commit {
  id: number;
  commitHash: string;
  author: string;
  message: string;
  reviewer: string;
  changes: string;
  date: string;
}

export interface DiffComment {
  author: string;
  text: string;
  isAI: boolean;
}

export interface DiffBlock {
  oldLine: number | null;
  newLine: number | null;
  content: string;
  type: "context" | "addition" | "deletion";
  comments?: DiffComment[];
}

export interface CommitDetail extends Commit {
  description: string;
  diff: string;
  diffBlocks: DiffBlock[];
  repositoryId: number | null;
  repositoryName: string | null;
  reviewCount: number;
}

function normalizeCommit(commit: any): Commit {
  return {
    id: commit.id,
    commitHash: commit.commit_hash,
    author: commit.author_name || commit.author_github_id || "unknown",
    message: commit.message || "",
    reviewer: commit.committer_name || commit.committer_github_id || "pending",
    changes: "View",
    date: commit.committed_date || commit.timestamp || commit.created_at,
  };
}

export async function getCommits(repoId: number): Promise<Commit[]> {
  const response = await apiClient.get<any[]>(`/commits/?repo_id=${repoId}`);
  return response.data.map(normalizeCommit);
}

export async function getCommitDetail(commitHash: string): Promise<CommitDetail> {
  const response = await apiClient.get<any>(`/commits/${commitHash}/`);
  const commit = normalizeCommit(response.data);
  return {
    ...commit,
    description: response.data.message || "",
    diff: response.data.url || "",
    diffBlocks: [],
    repositoryId: response.data.repository?.id || null,
    repositoryName: response.data.repository?.repo_name || null,
    reviewCount: response.data.review_count || response.data.reviews?.length || 0,
  };
}
