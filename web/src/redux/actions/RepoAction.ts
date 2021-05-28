import { createAsyncThunk } from '@reduxjs/toolkit';
import {
  createRepository,
  CreateRepoPayload,
  fetchRepoDetails,
  fetchReposFromApi,
  fetchRepoSettings,
  RepoSettings,
  updateRepoSettings,
} from "../../api/ReposApi";

export const fetchRepos = createAsyncThunk('repos/fetchRepos', async () => {
  const repos = await fetchReposFromApi();
  return repos;
});

export const fetchRepoDetailsAction = createAsyncThunk(
  'repos/fetchRepoDetails',
  async (repoId: number) => {
    const repoDetails = await fetchRepoDetails(repoId);
    return repoDetails;
  }
);

export const createRepositoryAction = createAsyncThunk(
  'repos/createRepository',
  async (payload: CreateRepoPayload) => {
    return createRepository(payload);
  }
);

export const fetchRepoSettingsAction = createAsyncThunk(
  'repos/fetchRepoSettings',
  async (repoId: number) => {
    const settings = await fetchRepoSettings(repoId);
    return { repoId, settings };
  }
);

export const updateRepoSettingsAction = createAsyncThunk(
  'repos/updateRepoSettings',
  async ({
    repoId,
    settings,
    metadata,
  }: {
    repoId: number;
    settings: RepoSettings;
    metadata?: { name?: string; description?: string };
  }) => {
    const updatedRepo = await updateRepoSettings(repoId, settings, metadata);
    return updatedRepo;
  }
);
