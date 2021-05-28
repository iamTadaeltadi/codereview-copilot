import { createAsyncThunk } from '@reduxjs/toolkit';
import { fetchPRDetails, fetchPullRequests } from '../../api/PullRequestApi';

export const fetchPullRequestsAction = createAsyncThunk(
  'pullRequests/fetchPullRequests',
  async (repoId: number) => {
    const pullRequests = await fetchPullRequests(repoId);
    return { repoId, pullRequests };
  }
);

export const fetchPRDetailsAction = createAsyncThunk(
  'pullRequests/fetchPRDetails',
  async ({ repoId, prNumber }: { repoId: number; prNumber: number }) => {
    const prDetails = await fetchPRDetails(repoId, prNumber);
    return { repoId, prNumber, prDetails };
  }
);
