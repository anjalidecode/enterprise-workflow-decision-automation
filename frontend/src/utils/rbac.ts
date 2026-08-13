import type { Role, WorkflowType } from '../types/api'

export type NavItem = {
  to: string
  label: string
  roles: Role[]
  icon: string
}

/** Frontend visibility only — backend RBAC remains authoritative. */
export const NAV_ITEMS: NavItem[] = [
  {
    to: '/dashboard',
    label: 'Dashboard',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'dashboard',
  },
  {
    to: '/workflows',
    label: 'Workflows',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'workflows',
  },
  {
    to: '/approvals',
    label: 'Approvals',
    roles: ['manager', 'hr', 'admin'],
    icon: 'approvals',
  },
  {
    to: '/employees',
    label: 'Employees',
    roles: ['hr', 'admin'],
    icon: 'employees',
  },
  {
    to: '/leave',
    label: 'Leave',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'leave',
  },
  {
    to: '/attendance',
    label: 'Attendance',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'attendance',
  },
  {
    to: '/recruitment',
    label: 'Recruitment',
    roles: ['manager', 'hr', 'admin'],
    icon: 'recruitment',
  },
  {
    to: '/onboarding',
    label: 'Onboarding',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'onboarding',
  },
  {
    to: '/performance',
    label: 'Performance',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'performance',
  },
  {
    to: '/training',
    label: 'Training',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'training',
  },
  {
    to: '/offboarding',
    label: 'Offboarding',
    roles: ['hr', 'admin'],
    icon: 'offboarding',
  },
  {
    to: '/hr-services',
    label: 'HR Services',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'services',
  },
  {
    to: '/audit',
    label: 'Audit',
    roles: ['hr', 'admin'],
    icon: 'audit',
  },
  {
    to: '/settings',
    label: 'Settings',
    roles: ['employee', 'manager', 'hr', 'admin'],
    icon: 'settings',
  },
]

export const EMPLOYEE_ALLOWED_WORKFLOW_TYPES: WorkflowType[] = [
  'leave_attendance',
  'attendance',
  'training',
  'onboarding',
  'hr_services',
  'performance',
]

export const APPROVER_ROLES: Role[] = ['manager', 'hr', 'admin']

export function navForRole(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role))
}

export function canApprove(role: Role): boolean {
  return APPROVER_ROLES.includes(role)
}

export function canRunWorkflowType(role: Role, workflowType: string): boolean {
  if (role === 'employee') {
    return EMPLOYEE_ALLOWED_WORKFLOW_TYPES.includes(workflowType)
  }
  return true
}

export function roleLabel(role: Role): string {
  switch (role) {
    case 'employee':
      return 'Employee'
    case 'manager':
      return 'Manager'
    case 'hr':
      return 'HR'
    case 'admin':
      return 'Admin'
    default:
      return role
  }
}
