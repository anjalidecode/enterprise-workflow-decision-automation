import { apiRequest } from './client'
import type {
  ApprovalRequest,
  HealthResponse,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
  Workflow,
  WorkflowAudit,
  WorkflowListResponse,
  WorkflowMetrics,
  WorkflowRunRequest,
  WorkflowTypeResponse,
} from '../types/api'

export const authApi = {
  login(body: LoginRequest): Promise<TokenResponse> {
    return apiRequest<TokenResponse>('/auth/login', {
      method: 'POST',
      body,
      token: null,
    })
  },
  register(body: RegisterRequest): Promise<{ message: string; user: User }> {
    return apiRequest<{ message: string; user: User }>('/auth/register', {
      method: 'POST',
      body,
      token: null,
    })
  },
  me(token?: string | null): Promise<User> {
    return apiRequest<User>('/auth/me', { token })
  },
}

export const healthApi = {
  check(): Promise<HealthResponse> {
    return apiRequest<HealthResponse>('/health', { token: null })
  },
}

export type ListWorkflowsParams = {
  workflow_type?: string
  status?: string
  limit?: number
  offset?: number
}

export const workflowsApi = {
  listTypes(): Promise<WorkflowTypeResponse> {
    return apiRequest<WorkflowTypeResponse>('/workflows/types')
  },
  list(params: ListWorkflowsParams = {}): Promise<WorkflowListResponse> {
    const query = new URLSearchParams()
    if (params.workflow_type) query.set('workflow_type', params.workflow_type)
    if (params.status) query.set('status', params.status)
    if (params.limit != null) query.set('limit', String(params.limit))
    if (params.offset != null) query.set('offset', String(params.offset))
    const qs = query.toString()
    return apiRequest<WorkflowListResponse>(`/workflows${qs ? `?${qs}` : ''}`)
  },
  get(workflowId: string): Promise<Workflow> {
    return apiRequest<Workflow>(`/workflows/${encodeURIComponent(workflowId)}`)
  },
  run(body: WorkflowRunRequest): Promise<Workflow> {
    return apiRequest<Workflow>('/workflows/run', {
      method: 'POST',
      body,
    })
  },
  audit(workflowId: string): Promise<WorkflowAudit> {
    return apiRequest<WorkflowAudit>(
      `/workflows/${encodeURIComponent(workflowId)}/audit`,
    )
  },
  metrics(workflowId: string): Promise<WorkflowMetrics> {
    return apiRequest<WorkflowMetrics>(
      `/workflows/${encodeURIComponent(workflowId)}/metrics`,
    )
  },
  approve(workflowId: string, body: ApprovalRequest = {}): Promise<Workflow> {
    return apiRequest<Workflow>(
      `/workflows/${encodeURIComponent(workflowId)}/approve`,
      { method: 'POST', body },
    )
  },
  reject(workflowId: string, body: ApprovalRequest = {}): Promise<Workflow> {
    return apiRequest<Workflow>(
      `/workflows/${encodeURIComponent(workflowId)}/reject`,
      { method: 'POST', body },
    )
  },
}
