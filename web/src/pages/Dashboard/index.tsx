import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../redux/store';
import { fetchRepos } from '../../redux/actions/RepoAction';
import { FiActivity, FiGitBranch, FiLink, FiPlus, FiSearch, FiSettings } from 'react-icons/fi';

const UserDashboard: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const { repos, status, error } = useSelector((state: RootState) => state.repos);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (status === 'idle') {
      dispatch(fetchRepos());
    }
  }, [dispatch, status]);

  const filteredRepos = useMemo(
    () => repos.filter((repo) => repo.name.toLowerCase().includes(searchTerm.toLowerCase())),
    [repos, searchTerm],
  );

  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-blue-600 animate-pulse"></div>
          <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-t-2 border-blue-600 animate-spin"></div>
        </div>
        <p className="text-gray-500 animate-pulse">Loading repositories...</p>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-sm border border-red-200">
          <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full">
            <FiActivity className="w-6 h-6 text-red-600" />
          </div>
          <h3 className="mt-4 text-lg font-medium text-center text-gray-900">Error Loading Data</h3>
          <p className="mt-2 text-sm text-center text-gray-500">{error}</p>
          <button
            onClick={() => dispatch(fetchRepos())}
            className="mt-4 w-full px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700"
          >
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
          <h1 className="text-2xl font-semibold text-gray-900">Repositories</h1>
          <p className="mt-1 text-sm text-gray-500">Monitor registered repositories, webhook readiness, and review configuration.</p>
        </div>
        <button
          onClick={() => navigate('/repo-registration')}
          className="inline-flex items-center px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-500/20 transition-all duration-200 shadow-sm group"
        >
          <FiPlus className="mr-2 group-hover:scale-110 transition-transform duration-200" />
          Add Repository
        </button>
      </div>

      <div className="mb-6 relative max-w-md">
        <FiSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 pointer-events-none" />
        <input
          type="text"
          placeholder="Search repositories..."
          className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="grid grid-cols-12 gap-4 text-xs font-medium text-gray-500 uppercase tracking-wider">
            <div className="col-span-4">Repository</div>
            <div className="col-span-4">Description</div>
            <div className="col-span-2">Webhook</div>
            <div className="col-span-2 text-right">Action</div>
          </div>
        </div>

        <div className="divide-y divide-gray-200">
          {filteredRepos.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <FiGitBranch className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-lg font-medium text-gray-900">No repositories found</h3>
              <p className="mt-1 text-sm text-gray-500">Try adjusting your search or register your first repository.</p>
            </div>
          ) : (
            filteredRepos.map((repo) => (
              <div
                key={repo.id}
                className="grid grid-cols-12 gap-4 items-center px-6 py-4 hover:bg-gray-50 transition-colors duration-150"
              >
                <div className="col-span-4 min-w-0">
                  <button
                    onClick={() => navigate(`/repos/${repo.id}`)}
                    className="flex items-center gap-2 text-left text-gray-900 hover:text-blue-600"
                  >
                    <FiGitBranch className="text-gray-400" />
                    <span className="font-medium truncate">{repo.name}</span>
                  </button>
                  {repo.repoUrl ? (
                    <div className="mt-1 flex items-center gap-1 text-xs text-gray-500 truncate">
                      <FiLink />
                      <span className="truncate">{repo.repoUrl}</span>
                    </div>
                  ) : null}
                </div>
                <div className="col-span-4 text-sm text-gray-600">
                  {repo.description || <span className="text-gray-400 italic">No description provided</span>}
                </div>
                <div className="col-span-2">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      repo.webhookStatus ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'
                    }`}
                  >
                    {repo.webhookStatus ? 'Configured' : 'Pending'}
                  </span>
                </div>
                <div className="col-span-2 flex justify-end">
                  <button
                    onClick={() => navigate(`/repos/${repo.id}/settings`)}
                    className="inline-flex items-center px-3 py-2 text-sm text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100"
                  >
                    <FiSettings className="mr-2" />
                    Settings
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default UserDashboard;
/* Feature: Add loading states */ 
