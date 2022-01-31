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
    name: repo.repo_name,
    repoUrl: repo.repo_url || "",
    description: repo.description || "",
    language: repo.llm_preference || "Mixed",
    stars: 0,
    prStats: { open: 0, closed: 0, merged: 0 },
    totalCommits: 0,
    webhookStatus: Boolean(repo.webhook_last_event_at || repo.webhook_url),
    collaborators: [],
    isAdmin: Boolean(repo.owner?.is_admin),
    settings,
    stats: {
      pullRequests: 0,
      commits: 0,
      contributors: 0,
      reviewScore: "0%",
    },
    activities: [],
  };
}

export async function fetchReposFromApi(): Promise<RepoDetails[]> {
  const response = await apiClient.get<any[]>("/repositories/");
  return response.data.map(normalizeRepo);
}

export async function fetchRepoDetails(repoId: number): Promise<RepoDetails> {
  const response = await apiClient.get<any>(`/repositories/${repoId}/`);
  return normalizeRepo(response.data);
}

export async function createRepository(payload: CreateRepoPayload): Promise<RepoDetails> {
  const response = await apiClient.post<any>("/repositories/", {
    repo_name: payload.repoName,
    repo_url: payload.repoUrl,
    description: payload.description || "",
    coding_standards: payload.codingStandards,
    code_metrics: payload.codeMetrics,
    llm_preference: payload.llmPreference,
  });
  return normalizeRepo(response.data);
}

export async function fetchRepoSettings(repoId: number): Promise<RepoSettings> {
  const response = await apiClient.get(`/repositories/${repoId}/`);
  return normalizeRepo(response.data).settings!;
}

export async function updateRepoSettings(
  repoId: number,
  settings: RepoSettings,
  metadata?: { name?: string; description?: string },
): Promise<RepoDetails> {
  const response = await apiClient.patch<any>(`/repositories/${repoId}/`, {
    ...(metadata?.name ? { repo_name: metadata.name } : {}),
    ...(metadata?.description !== undefined ? { description: metadata.description } : {}),
    coding_standards: settings.codeStandards,
    code_metrics: settings.evaluationMetrics,
    llm_preference: settings.llmModel,
  });
  return normalizeRepo(response.data);
}
