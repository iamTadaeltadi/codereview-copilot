// src/redux/actions/CommitAction.ts

import { createAsyncThunk } from '@reduxjs/toolkit';
import { Commit, getCommits } from '../../api/CommitsApi';



// Thunk action for fetching commits
export const fetchCommits = createAsyncThunk<Commit[], number>(
  'commits/fetchCommits',
  async (id: number) => {
    const response = await getCommits(id);
    return response;
  }
);
