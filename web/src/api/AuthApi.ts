import { apiClient, buildAbsoluteUrl } from "./client";

export interface User {
  id: number;
  username: string;
  email: string | null;
  isAdmin: boolean;
  githubId: string | null;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

interface TokenResponse {
  access: string;
  refresh?: string;
}

function normalizeUser(payload: any): User {
  return {
    id: payload.id,
    username: payload.username || payload.email || "unknown",
    email: payload.email ?? null,
    isAdmin: Boolean(payload.is_admin),
    githubId: payload.github_id ?? null,
  };
}

export async function login(payload: LoginPayload): Promise<AuthResponse> {
  const tokenResponse = await apiClient.post<TokenResponse>("/auth/token/", {
    username: payload.email,
    password: payload.password,
  });
  const token = tokenResponse.data.access;
  const me = await apiClient.get<any>("/user/", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return {
    user: normalizeUser(me.data),
    token,
  };
}


export function getGitHubLoginUrl() {
  return buildAbsoluteUrl("/api/v1/auth/github/login/");
}
