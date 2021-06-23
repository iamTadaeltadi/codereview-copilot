import { configureStore } from '@reduxjs/toolkit';
import repoReducer from './slices/RepoSlice';
import authReducer from './slices/AuthSlice';
import pullRequestReducer from "../redux/slices/PullRequestsSlice"
import commitReducer from './slices/CommitsSlice';
import commitDetailReducer from './slices/CommitDetailSlice';
import codeReviewReducer from './slices/CodeReviewSlice';



const store = configureStore({
  reducer: {
    repos: repoReducer,
    auth: authReducer,
    pullRequests: pullRequestReducer,
    commits: commitReducer,
    commitDetail:commitDetailReducer,
    codeReview:codeReviewReducer
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

export default store;