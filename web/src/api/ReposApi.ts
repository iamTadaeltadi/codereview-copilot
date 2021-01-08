import { apiClient } from "./client";

export interface Collaborator {
  id: number;
  name: string;
  avatarUrl: string;
  role: "admin" | "maintainer" | "contributor" | "member" | "owner";
}

export interface RepoSettings {
  codeStandards: string[];
  evaluationMetrics: string[];
  llmModel: string;
  webhookUrl?: string;
  webhookEnabled: boolean;
}

export interface CreateRepoPayload {
  repoName: string;
  repoUrl: string;
  description?: string;
  codingStandards: string[];
  codeMetrics: string[];
  llmPreference: string;
}

export interface RepoDetails {
  id: number;
  name: string;
  repoUrl?: string;
  description: string;
  language: string;
  stars?: number;
  prStats: {
    open: number;
    closed: number;
    merged: number;
  };
  totalCommits: number;
  webhookStatus: boolean;
  collaborators?: Collaborator[];
  isAdmin?: boolean;
  settings?: RepoSettings;
  stats?: {
    pullRequests: number;
    commits: number;
    contributors: number;
    reviewScore: string;
  };
  activities?: any[];
}

function normalizeRepo(repo: any): RepoDetails {
  const settings: RepoSettings = {
    codeStandards: repo.coding_standards || [],
    evaluationMetrics: repo.code_metrics || [],
    llmModel: repo.llm_preference || "gpt-4",
    webhookUrl: repo.webhook_url || undefined,
    webhookEnabled: Boolean(repo.webhook_url),
  };

  return {
    id: repo.id,
