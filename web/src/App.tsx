// src/App.tsx
import React, { useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Outlet,
  Navigate,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { restoreAuth } from './redux/slices/AuthSlice';
import { RootState } from './redux/store';
import { SidebarProvider, useSidebar } from './contexts/SidebarContext';

import Sidebar from './components/Sidebar';
import './App.css';

import Dashboard from './pages/Dashboard';
import Repositories from './pages/Repositories';
import RepoRegistration from './pages/RepoRegistration';
import LoginPage from './pages/Login/index'

import RepoOverview from './pages/RepoOverview';
import RepoSettings from './pages/RepoSettings';
import PullRequestPage from './pages/Reviews';
import PullRequestDetailPage from './pages/ReviewDetail';

import CodeReviewPage from './pages/CodeReview/code-review';
import CommitDetail from './pages/CodeReview/commit-detail';
import CommitList from './pages/CodeReview/commit-list';

// Layout without sidebar (for auth pages like login)
const AuthLayout = () => (
  <div className="auth-layout">
    <Outlet />
  </div>
);

// Layout with sidebar (for main app pages)
const MainLayout = () => {
  const { isOpen } = useSidebar();
  
  return (
  <div className="flex">
    <Sidebar />
      <div className={`
        flex-1 min-h-screen
        transition-all duration-300
        ${isOpen ? 'ml-64' : 'ml-20'}
      `}>
        <div className="p-8">
      <Outlet />
        </div>
    </div>
  </div>
);
};

// Protected Route Component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = useSelector((state: RootState) => state.auth.token);
  const location = useLocation();

  if (!token) {
