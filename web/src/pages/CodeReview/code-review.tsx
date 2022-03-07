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

  if (loading) return <p className="mt-6 text-center">Loading…</p>;
  if (error) return <p className="mt-6 text-center text-red-600">{error}</p>;
  if (!review) return <p className="mt-6 text-center">No review data.</p>;

  return (
    <div className="max-w-6xl mx-auto p-4 bg-gray-50">
      <header className="mb-6 bg-white p-4 rounded shadow">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-bold">Review Workflow #{review.id}</h1>
            <p className="mt-2 text-sm text-gray-600">{review.contextLabel}</p>
          </div>
          <div className="text-sm text-gray-600 text-right">
            <div><strong>Status:</strong> {review.status}</div>
            <div><strong>Threads:</strong> {review.threadCount}</div>
            {review.contextRoute && (
              <Link to={review.contextRoute} className="mt-2 inline-block text-blue-700 hover:text-blue-900">
                Back to source item
              </Link>
            )}
            {review.errorMessage && <div className="text-red-600 mt-2 max-w-sm">{review.errorMessage}</div>}
          </div>
        </div>
      </header>

      <div className="card mb-6 bg-white p-4 rounded shadow">
        <h2 className="text-xl font-semibold mb-3">Summary</h2>
        <div className="flex gap-4 mb-4 flex-wrap">
          <span className="badge bg-red-600 px-3 py-2 rounded text-white">{syntaxIssues.length} Critical Issues</span>
          <span className="badge bg-yellow-500 px-3 py-2 rounded text-white">{standardIssues.length} Standards Issues</span>
          <span className="badge bg-blue-500 px-3 py-2 rounded text-white">{fixes.length} Suggested Fixes</span>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {Object.entries({
            "Code complexity": "Complexity",
            "Code duplication": "Duplication",
            "Code coverage": "Coverage"
          }).map(([key, label]) => {
            const ratings = finalSummaries.map((f: any) => {
              const val = (f.ratings as any)?.[key];
              return typeof val === 'string' ? parseInt(val, 10) : val;
            });

            const avgRating = ratings.length
              ? Math.round(ratings.reduce((sum: number, val: number) => sum + (val || 0), 0) / ratings.length)
              : 0;
            return (
              <div key={key} className="p-3 border rounded bg-gray-50">
                <h6 className="font-semibold mb-2">{label}</h6>
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div className="bg-blue-600 h-2.5 rounded-full" style={{ width: `${avgRating * 10}%` }}></div>
                </div>
                <div className="text-right text-sm mt-1">{avgRating}/10</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-1">
          <div className="bg-white rounded shadow p-4 sticky top-4">
            <h3 className="text-lg font-semibold mb-3">Review Report</h3>
            <div className="flex flex-col gap-2">
              <a href="#syntax-issues" className="flex justify-between px-3 py-2 bg-gray-100 rounded hover:bg-gray-200">
                Syntax Issues <span className="rounded px-2 bg-red-100 text-red-700">{syntaxIssues.length}</span>
              </a>
              <a href="#standards-issues" className="flex justify-between px-3 py-2 bg-gray-100 rounded hover:bg-gray-200">
                Standards Issues <span className="rounded px-2 bg-yellow-100 text-yellow-700">{standardIssues.length}</span>
              </a>
              <a href="#suggested-fixes" className="flex justify-between px-3 py-2 bg-gray-100 rounded hover:bg-gray-200">
