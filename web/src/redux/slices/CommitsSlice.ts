// src/redux/slices/CommitSlice.ts

import { createSlice } from '@reduxjs/toolkit';
import { fetchCommits } from '../actions/CommitAction';
import { Commit } from '../../api/CommitsApi';

interface CommitState {
  commits: Commit[];
  loading: boolean;
  error: string | null;
}

const initialState: CommitState = {
  commits: [],
  loading: false,
  error: null,
};

const commitSlice = createSlice({
  name: 'commits',
  initialState,
  reducers: {
    // You can add synchronous reducers here if needed.
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCommits.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchCommits.fulfilled, (state, action) => {
        state.loading = false;
        state.commits = action.payload;
      })
      .addCase(fetchCommits.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch commits';
      });
  },
});

export default commitSlice.reducer;
