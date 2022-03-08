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
              <th style={styles.thTd}>Author</th>
              <th style={styles.thTd}>Commit Message</th>
              <th style={styles.thTd}>Reviewer</th>
              <th style={styles.thTd}>Workflow</th>
              <th style={styles.thTd}>Date of Commit</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((commit) => (
              <tr key={commit.commitHash} style={styles.tr}>
                <td style={styles.thTd}>
                  <Link to={`/commit-detail/${commit.commitHash}`} style={{ color: "#007bff" }}>{commit.author}</Link>
                </td>
                <td style={styles.thTd}>{commit.message}</td>
                <td style={styles.thTd}>{commit.reviewer}</td>
                <td style={styles.thTd}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span>{formatWorkflowStatus(commit.workflowStatus)}</span>
                    <span style={{ color: '#6b7280', fontSize: 12 }}>{commit.workflowRuns} run{commit.workflowRuns === 1 ? '' : 's'}</span>
                  </div>
                </td>
                <td style={styles.thTd}>{new Date(commit.date).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

function summarizeHistory(history: Array<{ status: string }>) {
  if (history.length === 0) return { status: 'pending', count: 0 };
  return { status: history[0].status || 'pending', count: history.length };
}

function formatWorkflowStatus(status: string) {
  switch (status) {
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    case 'in_progress':
    case 'processing':
      return 'In progress';
    case 'unavailable':
      return 'Unavailable';
    default:
      return 'Pending';
  }
}

export default CommitList;

const styles: { [key: string]: React.CSSProperties } = {
  pageContainer: { padding: "32px", backgroundColor: "#f7f8fa", minHeight: "100vh", fontFamily: "sans-serif", display: "flex", flexDirection: "column", alignItems: "center" },
  header: { width: "100%", maxWidth: "1200px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" },
  commitTitle: { margin: 0, fontSize: "32px", color: "#333", fontWeight: "bold" },
  subtitle: { marginTop: 8, color: '#6b7280' },
  tableContainer: { width: "100%", maxWidth: "1200px", backgroundColor: "#fff", borderRadius: "8px", boxShadow: "0 4px 12px rgba(0,0,0,0.05)", overflow: "hidden" },
  table: { width: "100%", borderCollapse: "collapse" },
  thead: { backgroundColor: "#e9ecef" },
  thTd: { padding: "16px", textAlign: "left", fontSize: "16px", color: "#495057" },
  tr: { borderBottom: "1px solid #dee2e6" },
};
