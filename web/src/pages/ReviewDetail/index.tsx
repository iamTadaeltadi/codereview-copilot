import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../redux/store';
import { fetchPRDetailsAction } from '../../redux/actions/PullRequestAction';
import { FiGitPullRequest, FiGitCommit, FiCheck, FiX, FiMessageSquare, FiAlertCircle, FiArrowLeft, FiClock } from 'react-icons/fi';
import type { PRFileDiff, PRComment, PRReview } from '../../api/PullRequestApi';
import { getReviewHistory, ReviewHistoryEntry } from '../../api/CodeReviewAPi';

const PullRequestDetail: React.FC = () => {
  const { repoId, prNumber } = useParams<{ repoId: string; prNumber: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { currentPR, status, error } = useSelector((state: RootState) => state.pullRequests);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [reviewHistory, setReviewHistory] = useState<ReviewHistoryEntry[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    if (repoId && prNumber) {
      dispatch(fetchPRDetailsAction({ repoId: parseInt(repoId, 10), prNumber: parseInt(prNumber, 10) }));
    }
  }, [repoId, prNumber, dispatch]);

  useEffect(() => {
    if (!currentPR?.id) {
      setReviewHistory([]);
      return;
    }

    let isActive = true;
    setReviewLoading(true);
    setReviewError(null);

    getReviewHistory('pr', currentPR.id)
      .then((entries) => {
        if (isActive) {
          setReviewHistory(entries);
        }
      })
      .catch((err: any) => {
        if (isActive) {
          setReviewError(err?.message || 'Failed to load review workflow history.');
        }
      })
      .finally(() => {
        if (isActive) {
          setReviewLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [currentPR?.id]);

  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-blue-600 animate-pulse"></div>
          <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-t-2 border-blue-600 animate-spin"></div>
        </div>
        <p className="text-gray-500 animate-pulse">Loading pull request details...</p>
      </div>
    );
  }

  if (status === 'failed' || !currentPR) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-sm border border-red-200">
          <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full">
