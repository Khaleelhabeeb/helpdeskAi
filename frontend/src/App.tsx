import { Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Agents from './pages/Agents';
import Billing from './pages/Billing';
import Settings from './pages/Settings';
import AgentDeploy from './pages/AgentDeploy';
import { ProtectedRoute } from './lib/auth';
import AuthCallback from './pages/AuthCallback';

function RootRoute() {
  const params = new URLSearchParams(window.location.search);
  if (params.has('error') || params.has('code') || window.location.hash.includes('access_token=')) {
    return <AuthCallback />;
  }
  return <Landing />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRoute />} />
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/agents" element={<ProtectedRoute><Agents /></ProtectedRoute>} />
      <Route path="/agents/:agentId/deploy" element={<ProtectedRoute><AgentDeploy /></ProtectedRoute>} />
      <Route path="/billing" element={<ProtectedRoute><Billing /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
