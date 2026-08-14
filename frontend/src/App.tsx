import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { DashboardPage } from './pages/DashboardPage'
import { WorkflowsPage } from './pages/WorkflowsPage'
import { WorkflowDetailPage } from './pages/WorkflowDetailPage'
import { ApprovalsPage } from './pages/ApprovalsPage'
import { EmployeesPage } from './pages/EmployeesPage'
import { AuditPage } from './pages/AuditPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { SettingsPage } from './pages/SettingsPage'
import {
  AttendancePage,
  HrServicesPage,
  LeavePage,
  OffboardingPage,
  OnboardingPage,
  PerformancePage,
  RecruitmentPage,
  RequestsPage,
  TrainingPage,
} from './pages/DomainPages'
import { ProtectedRoute, PublicOnlyRoute } from './routes/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/leave" element={<LeavePage />} />
          <Route path="/attendance" element={<AttendancePage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/performance" element={<PerformancePage />} />
          <Route path="/training" element={<TrainingPage />} />
          <Route path="/hr-services" element={<HrServicesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute roles={['manager', 'hr', 'admin']} />}>
        <Route element={<AppLayout />}>
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/recruitment" element={<RecruitmentPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute roles={['hr', 'admin']} />}>
        <Route element={<AppLayout />}>
          <Route path="/employees" element={<EmployeesPage />} />
          <Route path="/offboarding" element={<OffboardingPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
