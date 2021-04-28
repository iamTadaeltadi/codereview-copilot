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
