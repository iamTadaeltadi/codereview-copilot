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
        reviewRuns: workflowByPr[pr.id]?.count || 0,
      }))
      .filter((pr: PullRequest) => {
        const matchesSearch = pr.title.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = statusFilter === 'all' || pr.status === statusFilter;
        return matchesSearch && matchesStatus;
      });
  }, [currentRepoPRs, workflowByPr, searchTerm, statusFilter]);

  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-blue-600 animate-pulse"></div>
          <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-t-2 border-blue-600 animate-spin"></div>
        </div>
        <p className="text-gray-500 animate-pulse">Loading pull requests...</p>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-sm border border-red-200">
          <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full">
            <FiAlertCircle className="w-6 h-6 text-red-600" />
          </div>
          <h3 className="mt-4 text-lg font-medium text-center text-gray-900">Error Loading Pull Requests</h3>
          <p className="mt-2 text-sm text-center text-gray-500">{error}</p>
          <button onClick={() => dispatch(fetchPullRequestsAction(parseInt(repoId!, 10)))} className="mt-4 w-full px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700">
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Pull Requests</h1>
          <p className="mt-1 text-sm text-gray-500">Review workflow status now reflects the backend review runs for each pull request.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="relative">
          <FiSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 pointer-events-none" />
          <input type="text" placeholder="Search pull requests..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="appearance-none bg-white border border-gray-200 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 cursor-pointer hover:bg-gray-50">
          <option value="all">All Status</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
          <option value="merged">Merged</option>
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="divide-y divide-gray-200">
          {filteredPRs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4"><FiGitPullRequest className="w-8 h-8 text-gray-400" /></div>
              <h3 className="text-lg font-medium text-gray-900">No pull requests found</h3>
              <p className="mt-1 text-sm text-gray-500">{searchTerm || statusFilter !== 'all' ? 'Try adjusting your search or filters' : 'There are no pull requests in this repository yet'}</p>
            </div>
          ) : filteredPRs.map((pr: PullRequest) => (
            <Link key={pr.id} to={`/repos/${repoId}/pulls/${pr.number}`} className="block hover:bg-gray-50 transition-colors duration-150">
              <div className="px-6 py-4">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0"><StatusIcon status={pr.status} /></div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-medium text-gray-900 truncate">{pr.title}</h3>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">#{pr.number}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                      <div className="flex items-center gap-1">
                        <img src={pr.author.avatarUrl} alt={pr.author.name} className="w-4 h-4 rounded-full" />
                        <span>{pr.author.name}</span>
                      </div>
                      <span>Created {new Date(pr.createdAt).toLocaleDateString()}</span>
                      <span>{pr.reviewRuns || 0} workflow run{pr.reviewRuns === 1 ? '' : 's'}</span>
                    </div>
                  </div>
                  <div className="flex-shrink-0"><WorkflowStatusBadge status={pr.workflowStatus || 'pending'} /></div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

function summarizeHistory(history: ReviewHistoryEntry[]) {
  if (history.length === 0) return { status: 'pending', count: 0 };
  const latest = history[0];
  return { status: latest.status || 'pending', count: history.length };
}

const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'merged':
      return <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center"><FiGitPullRequest className="w-4 h-4 text-purple-600" /></div>;
    case 'closed':
      return <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center"><FiX className="w-4 h-4 text-red-600" /></div>;
    default:
      return <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center"><FiGitPullRequest className="w-4 h-4 text-green-600" /></div>;
  }
};

const WorkflowStatusBadge = ({ status }: { status: string }) => {
  switch (status) {
    case 'completed':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700"><FiCheck className="w-3 h-3 mr-1" />Completed</span>;
    case 'failed':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700"><FiX className="w-3 h-3 mr-1" />Failed</span>;
    case 'in_progress':
    case 'processing':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700"><FiClock className="w-3 h-3 mr-1" />In progress</span>;
    case 'unavailable':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"><FiAlertCircle className="w-3 h-3 mr-1" />Unavailable</span>;
    default:
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-50 text-yellow-700"><FiClock className="w-3 h-3 mr-1" />Pending</span>;
  }
};

export default PullRequests;
