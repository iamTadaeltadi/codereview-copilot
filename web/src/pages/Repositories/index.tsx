import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../redux/store';
import { fetchRepos } from '../../redux/actions/RepoAction';
import { Link } from 'react-router-dom';
import { FiPlus, FiSearch, FiStar, FiCode, FiGitBranch } from 'react-icons/fi';

interface Repo {
  id: number;
  name: string;
  description?: string;
  language?: string;
  stars?: number;
}

const Repositories: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { repos, status, error } = useSelector((state: RootState) => state.repos);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (status === 'idle') {
      dispatch(fetchRepos());
    }
  }, [dispatch, status]);

  const filteredRepos = repos.filter((repo: Repo) =>
    repo.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-red-500 bg-red-50 px-6 py-4 rounded-lg border border-red-200">
          <p className="font-medium">Error occurred</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Repositories</h1>
            <p className="mt-1 text-sm text-gray-500">Manage and monitor your code repositories</p>
          </div>
        <Link
          to="/repo-registration"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200 shadow-sm"
        >
            <FiPlus className="mr-2" />
            Add Repository
        </Link>
      </div>

        {/* Search Section */}
        <div className="mb-6">
          <div className="relative">
            <FiSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search repositories..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full sm:w-96 pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200"
        />
          </div>
      </div>

        {/* Repositories List */}
      {filteredRepos.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <FiGitBranch className="w-12 h-12 text-gray-400 mb-4" />
            <p className="text-gray-500 text-lg">No repositories found</p>
            <p className="text-gray-400 text-sm mt-1">Try adjusting your search term</p>
          </div>
      ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr className="bg-gray-50">
                    <th scope="col" className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Repository
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Description
                    </th>
                    <th scope="col" className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Language
                    </th>
                    <th scope="col" className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Stars
                    </th>
              </tr>
            </thead>
                <tbody className="bg-white divide-y divide-gray-200">
              {filteredRepos.map((repo: Repo) => (
                    <tr key={repo.id} className="hover:bg-gray-50 transition-colors duration-150">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Link 
                          to={`/repos/${repo.id}`}
                          className="flex items-center text-sm font-medium text-blue-600 hover:text-blue-700"
                        >
                          <FiGitBranch className="mr-2 flex-shrink-0" />
                      {repo.name}
                    </Link>
                  </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-600 line-clamp-2">
                          {repo.description || 
                            <span className="text-gray-400 italic">No description provided</span>
                          }
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        {repo.language ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            <FiCode className="mr-1" />
                            {repo.language}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className="inline-flex items-center text-sm text-gray-600">
                          <FiStar className="mr-1" />
                          {repo.stars ?? 0}
                        </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
            </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default Repositories;
