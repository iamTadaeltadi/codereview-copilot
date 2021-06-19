import { createSlice } from '@reduxjs/toolkit';
import { fetchPullRequestsAction, fetchPRDetailsAction } from '../actions/PullRequestAction';
import type { PullRequest, PullRequestDetail } from '../../api/PullRequestApi';

interface PullRequestState {
  pullRequests: Record<number, PullRequest[]>;
  currentPR: PullRequestDetail | null;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: PullRequestState = {
  pullRequests: {},
  currentPR: null,
  status: 'idle',
  error: null
};

const pullRequestSlice = createSlice({
  name: 'pullRequests',
  initialState,
  reducers: {
    clearCurrentPR: (state) => {
      state.currentPR = null;
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPullRequestsAction.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchPullRequestsAction.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.pullRequests[action.payload.repoId] = action.payload.pullRequests;
      })
      .addCase(fetchPullRequestsAction.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to fetch pull requests';
      })
      .addCase(fetchPRDetailsAction.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchPRDetailsAction.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.currentPR = {
          ...action.payload.prDetails,
          status: action.payload.prDetails.state === 'closed'
            ? action.payload.prDetails.merged_at ? 'merged' : 'closed'
            : 'open'
        };
      })
      .addCase(fetchPRDetailsAction.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to fetch PR details';
      });
  }
});

export const { clearCurrentPR } = pullRequestSlice.actions;
export default pullRequestSlice.reducer;
