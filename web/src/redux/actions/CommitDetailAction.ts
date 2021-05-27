import { createAsyncThunk } from '@reduxjs/toolkit';
import { CommitDetail, getCommitDetail } from '../../api/CommitsApi';

export const fetchCommitDetail = createAsyncThunk<CommitDetail, string>(
  'commitDetail/fetchCommitDetail',
  async (commitHash: string) => {
    const response = await getCommitDetail(commitHash);
    return response;
  }
);
