import { createSlice } from '@reduxjs/toolkit';
import { fetchCommitDetail } from '../actions/CommitDetailAction';
import type { CommitDetail } from '../../api/CommitsApi';

interface CommitDetailState {
  detail: CommitDetail | null;
  loading: boolean;
  error: string | null;
}

const initialState: CommitDetailState = {
  detail: null,
  loading: false,
  error: null,
};

const commitDetailSlice = createSlice({
  name: 'commitDetail',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchCommitDetail.pending, (state) => {
        state.loading = true;
        state.error = null;
        state.detail = null;
      })
      .addCase(fetchCommitDetail.fulfilled, (state, action) => {
        state.loading = false;
        state.detail = action.payload;
      })
      .addCase(fetchCommitDetail.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to load commit details';
      });
  },
});

export default commitDetailSlice.reducer;
