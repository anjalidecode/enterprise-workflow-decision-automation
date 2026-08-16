/** TypeScript types mirroring the backend API schemas. */

export type Role = 'employee' | 'manager' | 'hr' | 'admin'
export type UserStatus = 'invited' | 'active' | 'inactive'

export type WorkflowType =
  | 'leave_attendance'
  | 'recruitment'
  | 'onboarding'
  | 'attendance'
  | 'performance'
  | 'training'
  | 'offboarding'
  | 'hr_services'
  | string

export interface User {
  user_id: string
  username: string
  organization_id: string
  role: Role
  employee_id: string | null
  full_name?: string | null
  status?: UserStatus
}

export interface ManagedUser {
  user_id: string
  username: string
  full_name: string | null
  organization_id: string
  role: Role
  employee_id: string | null
  status: UserStatus
  is_active: boolean
  created_at: string | null
}

export interface UserListResponse {
  users: ManagedUser[]
  total: number
  limit: number
  offset: number
}

export interface InviteUserRequest {
  full_name: string
  email: string
  role: Exclude<Role, 'admin'>
  employee_id?: string | null
}

export interface DirectoryEmployee {
  employee_id: string
  name: string
  department: string | null
  job_role: string | null
  employment_status: string | null
  bound_user_id: string | null
  bound_username: string | null
  available: boolean
}

export interface EmployeeDirectoryResponse {
  employees: DirectoryEmployee[]
}

export interface InviteUserResponse {
  message: string
  user: ManagedUser
  invitation: {
    expires_at: string
    activation_path: string
    activation_token: string
  }
}

export interface ActivateAccountRequest {
  token: string
  password: string
  confirm_password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  full_name: string
  email: string
  password: string
  confirm_password: string
  organization_name: string
}

export interface WorkflowDecision {
  outcome: string
  rationale: string
  confidence: number
  requires_human_approval: boolean
  executable: boolean
  entity_refs: Record<string, unknown>
  evidence: string[]
  blockers: string[]
  warnings: string[]
}

export interface WorkflowAudit {
  workflow_id: string
  organization_id: string
  workflow_type: string
  started_at: string
  completed_at: string
  status: string
  final_outcome: string
  agents: Record<string, unknown>[]
  tool_executions: Record<string, unknown>[]
  memory_accesses: Record<string, unknown>[]
  decision: Record<string, unknown>
  actions: Record<string, unknown>[]
  pending_actions: Record<string, unknown>[]
  errors: string[]
  approval_checkpoint: Record<string, unknown> | null
  llm?: Record<string, unknown>
}

export interface WorkflowMetrics {
  duration_ms: number
  agent_count: number
  tool_count: number
  tool_success_rate: number
  retry_count: number
  action_count: number
  action_success_rate: number
  validation_failed: boolean
  human_approval_required: boolean
  decision_confidence: number
  escalated: boolean
  workflow_type: string
  organization_id: string
  status: string
  success: boolean
}

export interface RequestUnderstanding {
  intent: string
  workflow_type: string
  request_kind: string
  summary_label: string
  needs_clarification: boolean
  clarification_question: string
  confidence: number
  entities: Record<string, unknown>
}

export interface Workflow {
  workflow_id: string
  workflow_type: string
  status: string
  current_stage: string
  organization_id: string
  decision: WorkflowDecision | null
  response: string
  actions: Record<string, unknown>[]
  pending_actions: Record<string, unknown>[]
  errors: string[]
  approval_status: string | null
  audit: WorkflowAudit | null
  metrics: WorkflowMetrics | null
  router_status: string | null
  request_id: string
  understanding?: RequestUnderstanding | null
}

export interface WorkflowSummary {
  workflow_id: string
  workflow_type: string
  status: string
  organization_id: string
  created_at: string
  outcome: string
  approval_status: string | null
}

export interface WorkflowListResponse {
  workflows: WorkflowSummary[]
  total: number
  limit: number
  offset: number
  note?: string
}

export interface WorkflowTypeItem {
  workflow_type: string
  name: string
  description: string
  version: string
}

export interface WorkflowTypeResponse {
  workflows: WorkflowTypeItem[]
}

export interface WorkflowRunRequest {
  request: string
  workflow_type?: string | null
}

export interface ApprovalRequest {
  reason?: string
}

export interface APIErrorDetail {
  code: string
  message: string
  request_id?: string
  details?: Record<string, unknown>
}

export interface APIError {
  error: APIErrorDetail
}

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
}
