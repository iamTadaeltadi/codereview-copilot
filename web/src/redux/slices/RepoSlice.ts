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
