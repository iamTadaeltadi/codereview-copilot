import axios from "axios";

const baseURL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export const apiClient = axios.create({
  baseURL: `${baseURL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const stored = localStorage.getItem("authUser");
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      const token = parsed?.token;
      if (token) {
        config.headers = config.headers || {};
        (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
      }
    } catch {
      localStorage.removeItem("authUser");
    }
  }
  return config;
});

export function buildAbsoluteUrl(path: string) {
  return `${baseURL}${path.startsWith("/") ? path : `/${path}`}`;
}
