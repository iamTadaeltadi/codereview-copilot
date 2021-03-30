import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../redux/store';
import { fetchCommitDetail } from '../../redux/actions/CommitDetailAction';
import { DiffBlock } from '../../api/CommitsApi';
import { getReviewHistory, ReviewHistoryEntry } from '../../api/CodeReviewAPi';
import { FiAlertCircle, FiCheck, FiClock, FiX } from 'react-icons/fi';

const CommitDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { detail, loading, error } = useSelector((state: RootState) => state.commitDetail);
  const [reviewHistory, setReviewHistory] = useState<ReviewHistoryEntry[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      dispatch(fetchCommitDetail(id));
    }
  }, [dispatch, id]);

  useEffect(() => {
    if (!detail?.commitHash) {
      setReviewHistory([]);
      return;
    }

    let isActive = true;
    setReviewLoading(true);
    setReviewError(null);

    getReviewHistory('commit', detail.commitHash)
      .then((entries) => {
        if (isActive) {
          setReviewHistory(entries);
        }
      })
      .catch((err: any) => {
        if (isActive) {
          setReviewError(err?.message || 'Failed to load commit review history.');
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
  }, [detail?.commitHash]);

  if (loading) return <div className="text-center mt-8 text-lg">Loading commit details...</div>;
  if (error) return <div className="text-center mt-8 text-lg text-red-600">Error: {error}</div>;
  if (!detail) return <div className="text-center mt-8 text-lg">No commit details found.</div>;

  return (
    <div className="max-w-5xl mx-auto mt-8 px-4 md:px-0">
