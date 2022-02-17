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
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

const AppRoutes = () => {
  const dispatch = useDispatch();
  const token = useSelector((state: RootState) => state.auth.token);
  const navigate = useNavigate();

  // Hydrate auth state from localStorage when app loads
  useEffect(() => {
    dispatch(restoreAuth());
  }, [dispatch]);

  // If logged in and on login page, redirect to dashboard
  const location = useLocation();
  useEffect(() => {
    if (token && location.pathname === '/') {
      navigate('/dashboard');
    }
  }, [token, location.pathname, navigate]);

  return (
    <Routes>
      {/* Public route (no sidebar) */}
      <Route element={<AuthLayout />}>
        <Route path="/" element={<LoginPage />} />
      </Route>

      {/* Private routes (with sidebar) */}
      <Route
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/repos/:repoId" element={<RepoOverview />} />
        <Route path="/repos/:repoId/settings" element={<RepoSettings />} />
        <Route path="/repositories" element={<Repositories />} />
        <Route path="/repo-registration" element={<RepoRegistration />} />
        <Route path="/repos/:repoId/pulls" element={<PullRequestPage />} />
        <Route path="/repos/:repoId/pulls/:prNumber" element={<PullRequestDetailPage />} />
        <Route path="/commit-list/:id" element={<CommitList />} />
        <Route path="/commit-detail/:id" element={<CommitDetail />} />
        <Route path="/commit-review/:id" element={<CodeReviewPage />} />
      </Route>
    </Routes>
  );
};

const App = () => {
  return (
  <Router>
      <SidebarProvider>
    <AppRoutes />
      </SidebarProvider>
  </Router>
);
};

export default App;
