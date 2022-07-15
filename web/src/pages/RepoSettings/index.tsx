import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import {
  FiAlertCircle,
  FiArrowLeft,
  FiCpu,
  FiInfo,
  FiLink,
  FiSave,
  FiSettings,
} from 'react-icons/fi';
import { AppDispatch, RootState } from '../../redux/store';
import { fetchRepoDetailsAction, updateRepoSettingsAction } from '../../redux/actions/RepoAction';
import { RepoSettings as ApiRepoSettings } from '../../api/ReposApi';

interface EditableSettings {
  name: string;
  description: string;
  codeStandards: string;
  evaluationMetrics: string;
  llmModel: string;
  webhookUrl: string;
}

const toEditableSettings = (repo: any): EditableSettings => ({
  name: repo.name || '',
  description: repo.description || '',
  codeStandards: repo.settings?.codeStandards?.join(', ') || '',
  evaluationMetrics: repo.settings?.evaluationMetrics?.join(', ') || '',
  llmModel: repo.settings?.llmModel || 'gpt-4',
  webhookUrl: repo.settings?.webhookUrl || '',
});

const parseList = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

const RepoSettingsPage: React.FC = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { currentRepo, status, error } = useSelector((state: RootState) => state.repos);
  const [settings, setSettings] = useState<EditableSettings>({
    name: '',
    description: '',
    codeStandards: '',
    evaluationMetrics: '',
    llmModel: 'gpt-4',
    webhookUrl: '',
  });

  useEffect(() => {
    if (repoId) {
      dispatch(fetchRepoDetailsAction(parseInt(repoId, 10)));
    }
  }, [repoId, dispatch]);

  useEffect(() => {
    if (currentRepo) {
      setSettings(toEditableSettings(currentRepo));
    }
  }, [currentRepo]);

  const parsed = useMemo(
    () => ({
      standards: parseList(settings.codeStandards),
      metrics: parseList(settings.evaluationMetrics),
    }),
    [settings.codeStandards, settings.evaluationMetrics],
  );

  const isSaving = status === 'loading' && Boolean(currentRepo);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoId) {
      return;
    }

    const apiSettings: ApiRepoSettings = {
      codeStandards: parsed.standards,
      evaluationMetrics: parsed.metrics,
      llmModel: settings.llmModel,
      webhookUrl: settings.webhookUrl || undefined,
      webhookEnabled: Boolean(settings.webhookUrl),
    };

    try {
      await dispatch(
        updateRepoSettingsAction({
          repoId: parseInt(repoId, 10),
          settings: apiSettings,
          metadata: {
            name: settings.name,
            description: settings.description,
          },
        }),
      ).unwrap();
    } catch (submitError) {
      console.error('Error updating repository settings', submitError);
    }
  };

  if (status === 'loading' && !currentRepo) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-blue-600 animate-pulse"></div>
          <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-t-2 border-blue-600 animate-spin"></div>
        </div>
        <p className="text-gray-500 animate-pulse">Loading repository settings...</p>
      </div>
    );
  }

  if (status === 'failed' && !currentRepo) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-sm border border-red-200">
          <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full">
            <FiAlertCircle className="w-6 h-6 text-red-600" />
          </div>
          <h3 className="mt-4 text-lg font-medium text-center text-gray-900">Error Loading Settings</h3>
          <p className="mt-2 text-sm text-center text-gray-500">{error}</p>
          <button
            onClick={() => repoId && dispatch(fetchRepoDetailsAction(parseInt(repoId, 10)))}
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
      <div className="mb-8">
        <Link
          to={`/repos/${repoId}`}
          className="inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors duration-200"
        >
          <FiArrowLeft className="mr-2" />
          Back to Repository
        </Link>
      </div>

      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Repository Settings</h1>
          <p className="mt-1 text-sm text-gray-500">
            These fields persist to the backend repository record. Collaborator access and Git provider visibility remain GitHub-managed.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-medium text-gray-900">General</h2>
            </div>
            <div className="p-6 grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">Repository Name</label>
                <input
                  id="name"
                  value={settings.name}
                  onChange={(e) => setSettings((prev) => ({ ...prev, name: e.target.value }))}
                  className="mt-1 block w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              <div>
                <label htmlFor="webhookUrl" className="block text-sm font-medium text-gray-700">Generated Webhook URL</label>
                <div className="mt-1 flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
                  <FiLink className="text-gray-400" />
                  <span className="truncate">{settings.webhookUrl || 'Will be available after repository registration.'}</span>
                </div>
              </div>

              <div className="sm:col-span-2">
                <label htmlFor="description" className="block text-sm font-medium text-gray-700">Description</label>
                <textarea
                  id="description"
                  rows={4}
                  value={settings.description}
                  onChange={(e) => setSettings((prev) => ({ ...prev, description: e.target.value }))}
                  className="mt-1 block w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center gap-2">
              <FiSettings className="text-gray-400" />
              <h2 className="text-lg font-medium text-gray-900">Review Policy</h2>
            </div>
            <div className="p-6 grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label htmlFor="llmModel" className="block text-sm font-medium text-gray-700">Preferred Model</label>
                <div className="relative mt-1">
                  <FiCpu className="absolute left-3 top-3 text-gray-400" />
                  <select
                    id="llmModel"
                    value={settings.llmModel}
                    onChange={(e) => setSettings((prev) => ({ ...prev, llmModel: e.target.value }))}
