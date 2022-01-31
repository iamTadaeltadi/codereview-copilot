import { apiClient } from "./client";
import { reviewReport } from "../constants/review-report-response";

export interface Issue {
  location: string;
  file: string;
  description?: string;
  standard?: string;
}

export interface SyntaxBlock { issues: Issue[] }
export interface StandardsBlock { issues: Issue[] }
export interface ErrorAnalysisIssue {
  type: string;
  locations: string[];
  descriptions: string[];
}
export interface ErrorAnalysisBlock {
  messages: string[];
  issues: {
    summary: string;
    file: string;
    issues: ErrorAnalysisIssue[];
  };
}
export interface FinalRatings {
  "Code complexity": string;
  "Code duplication": string;
  "Code coverage": string;
}
export interface FinalBlock {
  summary: string;
  file: string;
  ratings: FinalRatings;
  critical_issues: string[];
}
export interface RawReviewResponse {
  review: {
    syntax: SyntaxBlock[];
    standards: StandardsBlock[];
    error_analysis: ErrorAnalysisBlock[];
    final: FinalBlock[];
  };
  status: string;
  artifacts: { fixes: string[]; summary: string };
}
export interface ReviewComment {
  id: number;
  author: string;
  text: string;
  isAI: boolean;
  timestamp: string;
}
export interface ReviewThreadComment {
  id: number;
  author: string;
  text: string;
  isAI: boolean;
  timestamp: string;
  type: string;
}
export interface ReviewThread {
  id: number;
  threadId: string;
  title: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  commentCount: number;
  comments: ReviewThreadComment[];
}
export interface ReviewHistoryEntry {
  id: number;
  status: string;
  createdAt: string;
  updatedAt: string;
  errorMessage: string | null;
  threadCount: number;
  hasReviewData: boolean;
}
export interface CodeReview {
  id: number;
  prOrCommitId: number;
  status: string;
  contextType: "pull_request" | "commit" | "review";
  contextLabel: string;
  contextRoute: string | null;
  raw: RawReviewResponse;
  chatThread: ReviewComment[];
  reviewRating: number | null;
  reviewFeedback: string;
  threadCount: number;
  errorMessage: string | null;
  threads: ReviewThread[];
  activeThreadId: number | null;
}

function fallbackReviewPayload(status = "completed"): RawReviewResponse {
  return {
    ...reviewReport,
    status,
  };
}

function extractReviewPayload(review: any): RawReviewResponse {
  return review.review_data?.final_result || review.review_data || fallbackReviewPayload(review.status || "completed");
}

function normalizeThreadComment(comment: any): ReviewThreadComment {
  return {
    id: comment.id,
    author: comment.user?.username || comment.user?.email || 'unknown',
    text: comment.comment || '',
    isAI: Boolean(comment.user?.is_ai_user || comment.user?.is_staff || comment.type === 'response'),
    timestamp: comment.created_at,
    type: comment.type || 'note',
  };
}

function normalizeThread(thread: any): ReviewThread {
  const comments = (thread.comments || []).map(normalizeThreadComment).sort((a: ReviewThreadComment, b: ReviewThreadComment) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  return {
    id: thread.id,
    threadId: thread.thread_id,
    title: thread.title || `Thread ${thread.id}`,
    status: thread.status || 'open',
    createdAt: thread.created_at,
    updatedAt: thread.updated_at,
    commentCount: thread.comment_count || comments.length,
    comments,
  };
}

function flattenComments(threads: ReviewThread[]): ReviewComment[] {
  return threads
    .flatMap((thread) => thread.comments)
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map((comment) => ({
      id: comment.id,
      author: comment.author,
      text: comment.text,
      isAI: comment.isAI,
      timestamp: comment.timestamp,
    }));
}

function buildContextLabel(review: any): string {
  if (review.pull_request) {
    return `PR #${review.pull_request.pr_number} · ${review.pull_request.title}`;
  }
  if (review.commit) {
    return `${String(review.commit.commit_hash || "").slice(0, 12)} · ${review.commit.message || "Commit review"}`;
