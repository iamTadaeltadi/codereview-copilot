import React, { useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "../../redux/store";
import { fetchRepoDetailsAction } from "../../redux/actions/RepoAction";
import { FiGitBranch, FiGitPullRequest, FiGitCommit, FiUsers, FiSettings, FiActivity, FiAlertCircle } from "react-icons/fi";

const RepoOverview: React.FC = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const { currentRepo, status, error } = useSelector(
    (state: RootState) => state.repos
  );

  useEffect(() => {
    if (repoId) {
      dispatch(fetchRepoDetailsAction(parseInt(repoId)));
    }
  }, [repoId, dispatch]);

  if (status === "loading") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-blue-600 animate-pulse"></div>
          <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-t-2 border-blue-600 animate-spin"></div>
        </div>
        <p className="text-gray-500 animate-pulse">Loading repository details...</p>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-sm border border-red-200">
          <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full">
            <FiAlertCircle className="w-6 h-6 text-red-600" />
          </div>
          <h3 className="mt-4 text-lg font-medium text-center text-gray-900">Error Loading Repository</h3>
          <p className="mt-2 text-sm text-center text-gray-500">{error}</p>
          <button
            onClick={() => dispatch(fetchRepoDetailsAction(parseInt(repoId!)))}
            className="mt-4 w-full px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors duration-200"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!currentRepo) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
          <FiGitBranch className="w-8 h-8 text-gray-400" />
        </div>
        <h3 className="text-lg font-medium text-gray-900">Repository not found</h3>
        <p className="text-sm text-gray-500">The repository you're looking for doesn't exist or you don't have access.</p>
        <button
          onClick={() => navigate('/repositories')}
          className="mt-2 inline-flex items-center px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-colors duration-200"
        >
          View All Repositories
        </button>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2">
            <FiGitBranch className="text-gray-400" />
            <h1 className="text-2xl font-semibold text-gray-900">{currentRepo.name}</h1>
          </div>
          <p className="mt-1 text-sm text-gray-500">{currentRepo.description || 'No description provided'}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to={`/repos/${repoId}/settings`}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors duration-200"
          >
            <FiSettings className="mr-2" />
            Settings
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<FiGitPullRequest className="w-5 h-5 text-blue-600" />}
          label="Pull Requests"
          value={currentRepo.stats?.pullRequests || 0}
          href={`/repos/${repoId}/pulls`}
        />
        <StatCard
          icon={<FiGitCommit className="w-5 h-5 text-green-600" />}
          label="Commits"
          value={currentRepo.stats?.commits || 0}
          href={`/commit-list/${repoId}`}
        />
        <StatCard
          icon={<FiUsers className="w-5 h-5 text-purple-600" />}
          label="Contributors"
          value={currentRepo.stats?.contributors || 0}
        />
        <StatCard
          icon={<FiActivity className="w-5 h-5 text-orange-600" />}
          label="Review Score"
          value={currentRepo.stats?.reviewScore || '0%'}
        />
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Recent Activity</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {currentRepo.activities?.length ? (
            currentRepo.activities.map((activity: any) => (
              <div key={activity.id} className="px-6 py-4 hover:bg-gray-50 transition-colors duration-150">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <img
                      src={activity.user.avatar}
                      alt={activity.user.name}
                      className="w-8 h-8 rounded-full"
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-900">
                      <span className="font-medium">{activity.user.name}</span>
                      {' '}{activity.action}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {activity.timestamp}
                    </p>
              </div>
              </div>
              </div>
            ))
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <FiActivity className="w-8 h-8 text-gray-400 mb-2" />
              <p className="text-gray-500">No recent activity</p>
            </div>
          )}
        </div>
      </div>
        </div>
  );
};

const StatCard = ({ icon, label, value, href }: { icon: React.ReactNode; label: string; value: number | string; href?: string }) => {
  const Content = () => (
    <div className="flex items-center justify-between p-6">
          <div className="flex items-center">
        <div className="flex-shrink-0">{icon}</div>
        <div className="ml-4">
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
        </div>
      </div>
      {href && (
        <div className="ml-4">
          <FiActivity className="w-5 h-5 text-gray-400" />
        </div>
      )}
    </div>
  );

  if (href) {
    return (
      <Link
        to={href}
        className="bg-white rounded-xl border border-gray-200 shadow-sm hover:border-blue-500/20 hover:ring-2 hover:ring-blue-500/20 transition-all duration-200"
      >
        <Content />
      </Link>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      <Content />
    </div>
  );
};

export default RepoOverview;
