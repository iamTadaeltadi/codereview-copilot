import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";
import { CodeReview, getCodeReview, ReviewComment } from "../../api/CodeReviewAPi";

interface CodeReviewState {
  review: CodeReview | null;
  loading: boolean;
  error  : string | null;
}

const initialState: CodeReviewState = { review: null, loading: false, error: null };

export const fetchCodeReview = createAsyncThunk<CodeReview, number>(
  "codeReview/fetchCodeReview",
  async (id) => getCodeReview(id)
);

const codeReviewSlice = createSlice({
  name: "codeReview",
  initialState,
  reducers: {
    addChatMessage(state, action: PayloadAction<ReviewComment>) {
      state.review?.chatThread.push(action.payload);
    },
    setReviewRating(state, action: PayloadAction<number>) {
      if (state.review) state.review.reviewRating = action.payload;
    },
    setReviewFeedback(state, action: PayloadAction<string>) {
      if (state.review) state.review.reviewFeedback = action.payload;
    },
    clearCodeReview(state) {
      state.review = null;
      state.error = null;
      state.loading = false;
    },
  },
  extraReducers: (builder) =>
    builder
      .addCase(fetchCodeReview.pending,  (s) => { s.loading = true; s.error = null; })
      .addCase(fetchCodeReview.fulfilled,(s,a)=>{ s.loading = false; s.review = a.payload; })
      .addCase(fetchCodeReview.rejected, (s,a)=>{ s.loading = false; s.error = a.error.message || "Failed"; })
});

export const { addChatMessage, setReviewRating, setReviewFeedback, clearCodeReview } = codeReviewSlice.actions;
export default codeReviewSlice.reducer;
