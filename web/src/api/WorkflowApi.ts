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
