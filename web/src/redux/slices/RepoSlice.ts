import { createSlice } from '@reduxjs/toolkit';
import {
  createRepositoryAction,
  fetchRepoDetailsAction,
  fetchRepoSettingsAction,
  fetchRepos,
  updateRepoSettingsAction,
} from '../actions/RepoAction';

interface RepoState {
  repos: any[];
  currentRepo: any | null;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: RepoState = {
  repos: [],
  currentRepo: null,
  status: 'idle',
  error: null,
};

const repoSlice = createSlice({
  name: 'repos',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchRepos.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchRepos.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.repos = action.payload;
      })
      .addCase(fetchRepos.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to fetch repos';
      })
      .addCase(fetchRepoDetailsAction.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchRepoDetailsAction.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.currentRepo = action.payload;
      })
      .addCase(fetchRepoDetailsAction.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to fetch repo details';
      })
      .addCase(createRepositoryAction.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(createRepositoryAction.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.repos = [action.payload, ...state.repos];
        state.currentRepo = action.payload;
      })
      .addCase(createRepositoryAction.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to create repository';
      })
      .addCase(fetchRepoSettingsAction.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchRepoSettingsAction.fulfilled, (state, action) => {
        state.status = 'succeeded';
        if (state.currentRepo && state.currentRepo.id === action.payload.repoId) {
          state.currentRepo.settings = action.payload.settings;
        }
      })
      .addCase(fetchRepoSettingsAction.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to fetch repo settings';
      })
      .addCase(updateRepoSettingsAction.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(updateRepoSettingsAction.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.currentRepo = action.payload;
        state.repos = state.repos.map((repo) =>
          repo.id === action.payload.id ? action.payload : repo,
        );
      })
      .addCase(updateRepoSettingsAction.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to update repo settings';
      });
  },
});

export default repoSlice.reducer;
