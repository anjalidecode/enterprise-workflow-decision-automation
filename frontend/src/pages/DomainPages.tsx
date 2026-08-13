import { Link } from 'react-router-dom'
import { StartWorkflowForm } from '../components/workflow/StartWorkflowForm'
import { useAuth } from '../context/AuthContext'

type DomainConfig = {
  pathLabel: string
  title: string
  description: string
  workflowType: string
  placeholder: string
}

const DOMAINS: Record<string, DomainConfig> = {
  leave: {
    pathLabel: 'Leave',
    title: 'Leave requests',
    description:
      'Run leave and attendance decision workflows for policy-aware time-off evaluation.',
    workflowType: 'leave_attendance',
    placeholder: 'Check whether employee E001 can take 3 days of leave starting next Monday.',
  },
  attendance: {
    pathLabel: 'Attendance',
    title: 'Attendance',
    description: 'Evaluate attendance anomalies, exceptions, and related HR decisions.',
    workflowType: 'attendance',
    placeholder: 'Review attendance exceptions for employee E001 this month.',
  },
  recruitment: {
    pathLabel: 'Recruitment',
    title: 'Recruitment',
    description: 'Source and shortlist candidates through the recruitment workflow.',
    workflowType: 'recruitment',
    placeholder: 'Find candidates for the Python Backend Developer position.',
  },
  onboarding: {
    pathLabel: 'Onboarding',
    title: 'Onboarding',
    description: 'Coordinate onboarding checklists, documents, and readiness decisions.',
    workflowType: 'onboarding',
    placeholder: 'Start onboarding checklist for a new hire joining Engineering.',
  },
  performance: {
    pathLabel: 'Performance',
    title: 'Performance',
    description: 'Run performance review and goal-related decision workflows.',
    workflowType: 'performance',
    placeholder: 'Evaluate performance goals progress for employee E001.',
  },
  training: {
    pathLabel: 'Training',
    title: 'Training',
    description: 'Recommend and validate training plans from skill gaps and catalog policy.',
    workflowType: 'training',
    placeholder: 'Recommend training courses for employee E001 to improve Python skills.',
  },
  offboarding: {
    pathLabel: 'Offboarding',
    title: 'Offboarding',
    description: 'Execute exit checklists and offboarding compliance decisions.',
    workflowType: 'offboarding',
    placeholder: 'Start offboarding process for employee E001.',
  },
  'hr-services': {
    pathLabel: 'HR Services',
    title: 'HR Services',
    description: 'Handle general HR service requests with policy-backed automation.',
    workflowType: 'hr_services',
    placeholder: 'Request an employment verification letter for employee E001.',
  },
}

export function DomainWorkflowPage({ domainKey }: { domainKey: keyof typeof DOMAINS }) {
  const config = DOMAINS[domainKey]
  const { user } = useAuth()

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <span>{config.pathLabel}</span>
          </div>
          <h1>{config.title}</h1>
          <p>{config.description}</p>
        </div>
      </div>
      <StartWorkflowForm
        defaultWorkflowType={config.workflowType}
        lockedType
        title={`Start ${config.pathLabel.toLowerCase()} workflow`}
        description={
          user?.role === 'employee'
            ? 'Self-service request. The backend enforces employee ownership rules.'
            : 'Enterprise request form backed by WorkflowEngine — not a chat interface.'
        }
        placeholder={config.placeholder}
      />
    </div>
  )
}

export function LeavePage() {
  return <DomainWorkflowPage domainKey="leave" />
}
export function AttendancePage() {
  return <DomainWorkflowPage domainKey="attendance" />
}
export function RecruitmentPage() {
  return <DomainWorkflowPage domainKey="recruitment" />
}
export function OnboardingPage() {
  return <DomainWorkflowPage domainKey="onboarding" />
}
export function PerformancePage() {
  return <DomainWorkflowPage domainKey="performance" />
}
export function TrainingPage() {
  return <DomainWorkflowPage domainKey="training" />
}
export function OffboardingPage() {
  return <DomainWorkflowPage domainKey="offboarding" />
}
export function HrServicesPage() {
  return <DomainWorkflowPage domainKey="hr-services" />
}
