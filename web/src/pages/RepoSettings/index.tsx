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
