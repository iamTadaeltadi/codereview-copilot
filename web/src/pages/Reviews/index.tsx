import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../redux/store';
import { fetchPullRequestsAction } from '../../redux/actions/PullRequestAction';
import { FiGitPullRequest, FiSearch, FiCheck, FiX, FiClock, FiAlertCircle } from 'react-icons/fi';
import type { PullRequest as APIPullRequest } from '../../api/PullRequestApi';
import { getReviewHistory, ReviewHistoryEntry } from '../../api/CodeReviewAPi';

interface PullRequest extends APIPullRequest {
  workflowStatus?: string;
  reviewRuns?: number;
}

const EMPTY_PULL_REQUESTS: APIPullRequest[] = [];

const PullRequests: React.FC = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { pullRequests, status, error } = useSelector((state: RootState) => state.pullRequests);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [workflowByPr, setWorkflowByPr] = useState<Record<number, { status: string; count: number }>>({});

  useEffect(() => {
    if (repoId) {
      dispatch(fetchPullRequestsAction(parseInt(repoId, 10)));
    }
  }, [repoId, dispatch]);

  const repoNumericId = parseInt(repoId || '0', 10);
  const currentRepoPRs = useMemo(
    () => pullRequests[repoNumericId] ?? EMPTY_PULL_REQUESTS,
    [pullRequests, repoNumericId],
  );

  useEffect(() => {
    if (currentRepoPRs.length === 0) {
      setWorkflowByPr({});
      return;
    }

    let isActive = true;
    Promise.all(
      currentRepoPRs.map(async (pr) => {
        try {
          const history = await getReviewHistory('pr', pr.id);
          return [pr.id, summarizeHistory(history)] as const;
        } catch {
          return [pr.id, { status: 'unavailable', count: 0 }] as const;
        }
      })
    ).then((entries) => {
      if (!isActive) return;
      setWorkflowByPr(Object.fromEntries(entries));
    });

    return () => {
      isActive = false;
    };
  }, [currentRepoPRs]);

  const filteredPRs = useMemo(() => {
    return currentRepoPRs
      .map((pr: APIPullRequest) => ({
        ...pr,
        workflowStatus: workflowByPr[pr.id]?.status,
