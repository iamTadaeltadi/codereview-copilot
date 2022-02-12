import { apiClient } from "./client";

export interface PullRequest {
  id: number;
  number: number;
  title: string;
  status: "open" | "closed" | "merged";
  createdAt: string;
  author: {
    name: string;
    avatarUrl: string;
  };
  repoId: number;
}

export interface PRFileDiff {
  id: string;
  filename: string;
  status: "added" | "modified" | "removed";
  additions: number;
  deletions: number;
  changes: number;
  patch: string;
  blob_url: string;
  raw_url: string;
  contents_url: string;
}

export interface PRComment {
  id: number;
  user: {
    login: string;
    avatar_url: string;
  };
  body: string;
  created_at: string;
  updated_at: string;
  path: string;
  line: number;
}

export interface PRReview {
  id: number;
  user: {
    login: string;
    avatar_url: string;
  };
  body: string;
  state: "APPROVED" | "CHANGES_REQUESTED" | "COMMENTED";
  submitted_at: string;
  html_url: string;
}

export interface PullRequestDetail {
  id: number;
  number: number;
  title: string;
  state: "open" | "closed";
  status?: "open" | "closed" | "merged";
  user: {
    login: string;
    avatar_url: string;
  };
  body: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  merged_at: string | null;
  merge_commit_sha: string;
  head: { ref: string; sha: string };
  base: { ref: string; sha: string };
  files: PRFileDiff[];
  comments: PRComment[];
  reviews: PRReview[];
}

function normalizePullRequest(pr: any, repoId: number): PullRequest {
  return {
    id: pr.id,
    number: pr.pr_number,
    title: pr.title,
    status: (pr.status || "open") as PullRequest["status"],
    createdAt: pr.created_at_gh || pr.created_at,
    author: {
      name: pr.user_login || pr.author_github_id || "unknown",
      avatarUrl: pr.user_avatar_url || "",
    },
    repoId,
  };
}

function normalizePullRequestDetail(pr: any): PullRequestDetail {
  const merged = Boolean(pr.merged_at_gh || pr.merged_at);
  const state = (pr.status || pr.state || "open") === "closed" ? "closed" : "open";
  return {
    id: pr.id,
    number: pr.pr_number || pr.number,
    title: pr.title,
    state,
    status: merged ? "merged" : state,
    user: {
      login: pr.user_login || pr.author_github_id || "unknown",
      avatar_url: pr.user_avatar_url || "",
    },
    body: pr.body || "",
    created_at: pr.created_at_gh || pr.created_at,
    updated_at: pr.updated_at_gh || pr.updated_at,
    closed_at: pr.closed_at_gh || null,
    merged_at: pr.merged_at_gh || null,
    merge_commit_sha: pr.head_sha || "",
    head: { ref: "", sha: pr.head_sha || "" },
    base: { ref: "", sha: pr.base_sha || "" },
    files: [],
    comments: [],
    reviews: [],
  };
}

export async function fetchPullRequests(repoId: number): Promise<PullRequest[]> {
  const response = await apiClient.get<any[]>(`/pull-requests/?repo_id=${repoId}`);
  return response.data.map((pr: any) => normalizePullRequest(pr, repoId));
}

export async function fetchPRDetails(repoId: number, prNumber: number): Promise<PullRequestDetail> {
  const response = await apiClient.get<any>(`/repositories/${repoId}/pulls/${prNumber}/`);
  return normalizePullRequestDetail(response.data);
}
