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
