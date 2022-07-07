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
      <header className="border-b pb-4 mb-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">{detail.message}</h1>
            <p className="mt-1 text-sm text-gray-500">
              <span className="font-semibold">Commit Hash:</span> {detail.commitHash}
              {' | '}
              <span className="font-semibold">Author:</span> {detail.author}
              {' | '}
              <span className="font-semibold">Date:</span> {new Date(detail.date).toLocaleString()}
            </p>
          </div>
          {detail.repositoryId && (
            <Link to={`/repos/${detail.repositoryId}`} className="text-sm text-blue-700 hover:text-blue-900">
              View repository
            </Link>
          )}
        </div>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="space-y-2 rounded-xl border border-gray-200 bg-white p-4">
          <div><strong>Repository:</strong> {detail.repositoryName || 'Unknown'}</div>
          <div><strong>Recorded reviews:</strong> {reviewHistory.length}</div>
          <div><strong>Changes:</strong> {detail.changes}</div>
          <div><strong>Reviewer field:</strong> <span className="italic">{detail.reviewer}</span></div>
        </div>
        <div className="space-y-2 rounded-xl border border-gray-200 bg-white p-4">
          <div><strong>Description:</strong> {detail.description || 'No commit description was captured.'}</div>
          <div><strong>Diff URL:</strong> {detail.diff ? <a className="text-blue-700" href={detail.diff} target="_blank" rel="noreferrer">Open source URL</a> : 'Unavailable'}</div>
          <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-900">
            AI review state is tracked through Review records. Use the history panel below to open a specific review run.
          </div>
        </div>
      </section>

      <section className="mb-6 rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="border-b px-4 py-3">
          <h2 className="text-xl font-semibold text-gray-700">Review Workflow</h2>
        </div>
        {reviewLoading ? (
          <div className="p-4 text-gray-500">Loading commit review history...</div>
        ) : reviewError ? (
          <div className="p-4 text-red-600">{reviewError}</div>
        ) : reviewHistory.length === 0 ? (
          <div className="p-4 text-gray-500">No review runs have been recorded for this commit yet.</div>
        ) : (
          <div className="divide-y">
            {reviewHistory.map((entry) => (
              <div key={entry.id} className="p-4 flex items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <ReviewStatusBadge status={entry.status} />
                    <span className="text-sm text-gray-500">Review #{entry.id}</span>
                  </div>
                  <div className="mt-2 text-sm text-gray-600 flex flex-wrap gap-4">
                    <span>Created {new Date(entry.createdAt).toLocaleString()}</span>
                    <span>{entry.threadCount} thread{entry.threadCount === 1 ? '' : 's'}</span>
                    <span>{entry.hasReviewData ? 'Findings available' : 'No report yet'}</span>
                  </div>
                  {entry.errorMessage && <div className="mt-2 text-sm text-red-600">{entry.errorMessage}</div>}
                </div>
                <Link to={`/commit-review/${entry.id}`} className="px-3 py-2 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-sm font-medium">
                  Open review
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      <h2 className="text-xl font-semibold mb-2 text-gray-700">Changes</h2>
      {detail.diffBlocks.length === 0 ? (
        <div className="border rounded p-4 text-gray-500">Structured diff blocks are not available in the current backend response for this commit yet.</div>
      ) : (
        <div className="border rounded">
          <table className="w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="py-2 px-3 text-left text-gray-600 w-12">Old</th>
                <th className="py-2 px-3 text-left text-gray-600 w-12">New</th>
                <th className="py-2 px-3 text-left text-gray-600">Code</th>
              </tr>
            </thead>
            <tbody>{detail.diffBlocks.map((block, index) => <DiffRow key={index} block={block} />)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default CommitDetail;

const DiffRow: React.FC<{ block: DiffBlock }> = ({ block }) => {
  let rowBg = 'bg-transparent';
  let textColor = 'text-gray-800';
  if (block.type === 'addition') { rowBg = 'bg-green-50'; textColor = 'text-green-800'; }
  else if (block.type === 'deletion') { rowBg = 'bg-red-50'; textColor = 'text-red-800'; }

  return (
    <tr className={`${rowBg} border-b border-gray-200`}>
      <td className="py-1 px-2 text-gray-500 text-right align-top w-10">{block.oldLine !== null ? block.oldLine : ''}</td>
      <td className="py-1 px-2 text-gray-500 text-right align-top w-10">{block.newLine !== null ? block.newLine : ''}</td>
      <td className={`py-1 px-2 whitespace-pre-wrap ${textColor}`}>{block.content}</td>
    </tr>
  );
};

const ReviewStatusBadge = ({ status }: { status: string }) => {
  switch (status) {
    case 'completed':
      return <span className="inline-flex items-center rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700"><FiCheck className="mr-1 h-3 w-3" />Completed</span>;
    case 'failed':
      return <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700"><FiX className="mr-1 h-3 w-3" />Failed</span>;
    case 'in_progress':
    case 'processing':
      return <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700"><FiClock className="mr-1 h-3 w-3" />In progress</span>;
    default:
      return <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"><FiAlertCircle className="mr-1 h-3 w-3" />Pending</span>;
  }
};
