import { createAsyncThunk } from "@reduxjs/toolkit";
import { CodeReview, getCodeReview } from "../../api/CodeReviewAPi";

export const fetchCodeReview = createAsyncThunk<CodeReview, number>(
    'codeReview/fetchCodeReview',
    async (id: number) => {
      const review = await getCodeReview(id);
      return review;
    }
  );
  