import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "../../redux/store";
import { clearCodeReview, fetchCodeReview } from "../../redux/slices/CodeReviewSlice";
import { createReviewThread, replyToReviewThread } from "../../api/CodeReviewAPi";

interface Issue {
  file: string;
  location: string;
  description?: string;
  standard?: string;
}

const flatten = <T,>(arr: { issues: T[] }[] = []) => arr.flatMap((b) => b.issues);

const CodeReviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { review, loading, error } = useSelector((s: RootState) => s.codeReview);
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      dispatch(fetchCodeReview(Number(id)));
    }
    return () => {
      dispatch(clearCodeReview());
    };
  }, [dispatch, id]);

  const reviewData = review?.raw.review || { syntax: [], standards: [], final: [] };
  const syntaxIssues = useMemo(() => flatten<Issue>(reviewData.syntax || []), [reviewData.syntax]);
  const standardIssues = useMemo(() => flatten<Issue>(reviewData.standards || []), [reviewData.standards]);
  const finalSummaries = reviewData.final || [];
  const fixes = review?.raw.artifacts?.fixes || [];

  const handleSendChat = async () => {
    if (!review || !chatInput.trim() || sending) return;

    setSending(true);
    setSendError(null);

    try {
      let threadId = review.activeThreadId;
      
      // Auto-create thread if none exists
      if (!threadId) {
        try {
          const thread = await createReviewThread(review.id, `Discussion for review ${review.id}`);
          threadId = thread.id;
        } catch (threadErr: any) {
          throw new Error(`Failed to create discussion thread: ${threadErr?.response?.data?.detail || threadErr?.message || 'Unknown error'}`);
        }
      }
      
      // Send the reply
      await replyToReviewThread(threadId, chatInput.trim());
      setChatInput("");
      
      // Refresh the review data to get the latest thread state
      await dispatch(fetchCodeReview(review.id)).unwrap();
      
    } catch (err: any) {
      const errorMessage = err?.response?.data?.detail || err?.message || 'Failed to send feedback to the review thread.';
      setSendError(errorMessage);
      console.error('Thread reply error:', err);
    } finally {
      setSending(false);
    }
  };
