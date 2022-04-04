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
