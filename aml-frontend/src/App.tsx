import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { LanguageProvider } from '@/contexts/LanguageContext';
import Layout from '@/components/Layout';
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import OnboardingPage from '@/pages/OnboardingPage';
import ScreeningPage from '@/pages/ScreeningPage';
import RiskPage from '@/pages/RiskPage';
import TransactionsPage from '@/pages/TransactionsPage';
import CasesPage from '@/pages/CasesPage';
import AuditPage from '@/pages/AuditPage';
import AnalyticsPage from '@/pages/AnalyticsPage';
import ComplianceInquiryPage from '@/pages/ComplianceInquiryPage';
import SearchPage from '@/pages/regulatory/SearchPage';
import ReviewQueuePage from '@/pages/regulatory/ReviewQueuePage';
import IntelligenceDashboard from '@/pages/IntelligenceDashboard';
import ControlsPage from '@/pages/phase4/ControlsPage';
import EvidencePage from '@/pages/phase4/EvidencePage';
import GapAnalysisPage from '@/pages/phase4/GapAnalysisPage';
import ExecutiveReportPage from '@/pages/phase4/ExecutiveReportPage';
import ControlSuggestionsPage from '@/pages/phase5a/ControlSuggestionsPage';
import EvidenceAlertsPage from '@/pages/phase5a/EvidenceAlertsPage';
import RiskTrendsDashboard from '@/pages/phase5b/RiskTrendsDashboard';
import PatternDetectionPage from '@/pages/phase5b/PatternDetectionPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 mt-3">Loading...</p>
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/" element={
        <ProtectedRoute>
          <Layout>
            <DashboardPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/onboarding" element={
        <ProtectedRoute>
          <Layout>
            <OnboardingPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/screening" element={
        <ProtectedRoute>
          <Layout>
            <ScreeningPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/risk" element={
        <ProtectedRoute>
          <Layout>
            <RiskPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/transactions" element={
        <ProtectedRoute>
          <Layout>
            <TransactionsPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/cases" element={
        <ProtectedRoute>
          <Layout>
            <CasesPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/audit" element={
        <ProtectedRoute>
          <Layout>
            <AuditPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/analytics" element={
        <ProtectedRoute>
          <Layout>
            <AnalyticsPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/compliance" element={
        <ProtectedRoute>
          <Layout>
            <ComplianceInquiryPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/reg-search" element={
        <ProtectedRoute>
          <Layout>
            <SearchPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/review-queue" element={
        <ProtectedRoute>
          <Layout>
            <ReviewQueuePage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/intelligence" element={
        <ProtectedRoute>
          <Layout>
            <IntelligenceDashboard />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/controls" element={
        <ProtectedRoute>
          <Layout>
            <ControlsPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/evidence" element={
        <ProtectedRoute>
          <Layout>
            <EvidencePage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/gap-analysis" element={
        <ProtectedRoute>
          <Layout>
            <GapAnalysisPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/executive-report" element={
        <ProtectedRoute>
          <Layout>
            <ExecutiveReportPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/control-suggestions" element={
        <ProtectedRoute>
          <Layout>
            <ControlSuggestionsPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/evidence-alerts" element={
        <ProtectedRoute>
          <Layout>
            <EvidenceAlertsPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/risk-trends" element={
        <ProtectedRoute>
          <Layout>
            <RiskTrendsDashboard />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="/pattern-detection" element={
        <ProtectedRoute>
          <Layout>
            <PatternDetectionPage />
          </Layout>
        </ProtectedRoute>
      } />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <LanguageProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </LanguageProvider>
    </BrowserRouter>
  );
}
