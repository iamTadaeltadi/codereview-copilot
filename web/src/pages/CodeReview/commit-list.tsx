import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "../../redux/store";
import { fetchCommits } from "../../redux/actions/CommitAction";
import { getReviewHistory } from "../../api/CodeReviewAPi";

const CommitList: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { commits, loading, error } = useSelector((state: RootState) => state.commits);
  const [workflowByCommit, setWorkflowByCommit] = useState<Record<string, { status: string; count: number }>>({});

  useEffect(() => {
    if (id) {
      dispatch(fetchCommits(Number(id)));
    }
  }, [dispatch, id]);

  useEffect(() => {
    if (commits.length === 0) {
      setWorkflowByCommit({});
      return;
    }

    let isActive = true;
    Promise.all(
      commits.map(async (commit) => {
        try {
          const history = await getReviewHistory('commit', commit.commitHash);
          return [commit.commitHash, summarizeHistory(history)] as const;
        } catch {
          return [commit.commitHash, { status: 'unavailable', count: 0 }] as const;
        }
      })
    ).then((entries) => {
      if (!isActive) return;
      setWorkflowByCommit(Object.fromEntries(entries));
    });

    return () => {
      isActive = false;
    };
  }, [commits]);

  const rows = useMemo(() => commits.map((commit) => ({
    ...commit,
    workflowStatus: workflowByCommit[commit.commitHash]?.status || 'pending',
    workflowRuns: workflowByCommit[commit.commitHash]?.count || 0,
  })), [commits, workflowByCommit]);

  if (loading) return <div className="text-center mt-8 text-lg">Loading commits...</div>;
  if (error) return <div className="text-center mt-8 text-lg text-red-600">Error: {error}</div>;

  return (
    <div style={styles.pageContainer}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.commitTitle}>Commit List</h1>
          <p style={styles.subtitle}>Workflow status is derived from backend commit review history.</p>
        </div>
      </div>
      <div style={styles.tableContainer}>
        <table style={styles.table}>
          <thead style={styles.thead}>
            <tr>
