import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { FaArrowLeft, FaCode, FaGithub, FaLink, FaRobot } from 'react-icons/fa';
import { AppDispatch, RootState } from '../../redux/store';
import { createRepositoryAction } from '../../redux/actions/RepoAction';

const parseList = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

const RepoRegistration = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const { status, error } = useSelector((state: RootState) => state.repos);
  const [formData, setFormData] = useState({
    repo_name: '',
    repo_url: '',
    description: '',
    coding_standards: '',
    code_metrics: '',
    llm_preference: 'gpt-4',
  });

  const isSubmitting = status === 'loading';
  const parsedPreview = useMemo(
    () => ({
      standards: parseList(formData.coding_standards),
      metrics: parseList(formData.code_metrics),
    }),
    [formData.coding_standards, formData.code_metrics],
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const createdRepo = await dispatch(
        createRepositoryAction({
          repoName: formData.repo_name,
          repoUrl: formData.repo_url,
          description: formData.description,
          codingStandards: parsedPreview.standards,
          codeMetrics: parsedPreview.metrics,
          llmPreference: formData.llm_preference,
        }),
      ).unwrap();
      navigate(`/repos/${createdRepo.id}`);
    } catch (submitError) {
      console.error('Repository creation failed', submitError);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="mb-8">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors duration-200"
        >
          <FaArrowLeft className="mr-2" />
          <span>Back</span>
        </button>
      </div>

      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900">Register a New Repository</h1>
          <p className="mt-3 text-gray-500">
            Add a GitHub repository so the backend can track pull requests, commits, and review jobs.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <FormField
              label="Repository Name"
              name="repo_name"
              icon={<FaGithub className="text-gray-400" />}
              placeholder="owner/repository"
              value={formData.repo_name}
              onChange={handleChange}
              helper="Required format: owner/repository"
            />

            <FormField
              label="Repository URL"
              name="repo_url"
              icon={<FaLink className="text-gray-400" />}
              placeholder="https://github.com/owner/repository"
              value={formData.repo_url}
              onChange={handleChange}
              helper="Public GitHub URL used for webhook and metadata lookups"
            />

            <div className="space-y-2 md:col-span-2">
              <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                id="description"
                name="description"
                rows={3}
                value={formData.description}
                onChange={handleChange}
                placeholder="Short description of the repository"
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200"
              />
            </div>

            <FormField
              label="Coding Standards"
              name="coding_standards"
              icon={<FaCode className="text-gray-400" />}
              placeholder="e.g., DRY, SOLID, secure input validation"
              value={formData.coding_standards}
              onChange={handleChange}
              helper="Comma-separated review standards"
            />

            <FormField
              label="Code Metrics"
              name="code_metrics"
              icon={<FaCode className="text-gray-400" />}
              placeholder="e.g., complexity, duplication, testability"
              value={formData.code_metrics}
              onChange={handleChange}
              helper="Comma-separated metrics the review agents should emphasize"
            />

            <div className="space-y-2 md:col-span-2">
              <label className="block text-sm font-medium text-gray-700">
                <span className="flex items-center gap-2">
                  <FaRobot className="text-gray-400" />
                  LLM Preference
                </span>
              </label>
              <select
                name="llm_preference"
                value={formData.llm_preference}
                onChange={handleChange}
                className="w-full px-4 py-2.5 bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200"
              >
                <option value="gpt-4">GPT-4</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="claude-3.5-sonnet">Claude 3.5 Sonnet</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">Stored on the repository record and used by review services.</p>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600 space-y-2">
            <p>Webhook URL is generated automatically by the backend after registration.</p>
            <p>Parsed standards: {parsedPreview.standards.length ? parsedPreview.standards.join(', ') : 'none'}</p>
            <p>Parsed metrics: {parsedPreview.metrics.length ? parsedPreview.metrics.join(', ') : 'none'}</p>
          </div>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          ) : null}

          <div className="pt-6 border-t border-gray-200 flex items-center justify-between gap-4">
            <p className="text-sm text-gray-500">Repository name and repository URL must both match the GitHub repository you want to register.</p>
            <button
              type="submit"
              disabled={isSubmitting}
              className={`inline-flex items-center justify-center px-6 py-3 bg-blue-600 text-white text-sm font-semibold rounded-lg shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200 ${
                isSubmitting ? 'opacity-80 cursor-not-allowed' : ''
              }`}
            >
              {isSubmitting ? 'Registering...' : 'Register Repository'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const FormField = ({
  label,
  name,
  icon,
  placeholder,
  value,
  onChange,
  helper,
}: {
  label: string;
  name: string;
  icon: React.ReactNode;
  placeholder?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  helper?: string;
}) => (
  <div className="space-y-2">
    <label htmlFor={name} className="block text-sm font-medium text-gray-700">
      <span className="flex items-center gap-2">{icon} {label}</span>
    </label>
    <div className="relative">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">{icon}</div>
      <input
        id={name}
        name={name}
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={onChange}
        className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200"
        required
      />
    </div>
    {helper ? <p className="text-xs text-gray-500">{helper}</p> : null}
  </div>
);

export default RepoRegistration;
