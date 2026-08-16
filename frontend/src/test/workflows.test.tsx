import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import App from '../App'
import { setStoredToken } from '../api/client'
import { demoUsers, jsonResponse, renderWithProviders } from './testUtils'
import type { Workflow, WorkflowSummary } from '../types/api'

const sampleSummary: WorkflowSummary = {
  workflow_id: 'wf-001',
  workflow_type: 'leave_attendance',
  status: 'awaiting_human_approval',
  organization_id: 'demo-org',
  created_at: '2026-08-14T01:00:00Z',
  outcome: 'approve_with_conditions',
  approval_status: 'awaiting',
}

const sampleWorkflow: Workflow = {
  workflow_id: 'wf-001',
  workflow_type: 'leave_attendance',
  status: 'awaiting_human_approval',
  current_stage: 'action',
  organization_id: 'demo-org',
  decision: {
    outcome: 'approve_with_conditions',
    rationale: 'Within policy',
    confidence: 0.86,
    requires_human_approval: true,
    executable: true,
    entity_refs: {},
    evidence: ['policy match'],
    blockers: [],
    warnings: ['low coverage week'],
  },
  response: 'Pending manager approval',
  actions: [],
  pending_actions: [{ type: 'notify' }],
  errors: [],
  approval_status: 'awaiting',
  audit: {
    workflow_id: 'wf-001',
    organization_id: 'demo-org',
    workflow_type: 'leave_attendance',
    started_at: '2026-08-14T01:00:00Z',
    completed_at: '',
    status: 'awaiting_human_approval',
    final_outcome: 'approve_with_conditions',
    agents: [
      { name: 'planner', status: 'completed', order: 1 },
      { name: 'decision', status: 'completed', order: 5 },
    ],
    tool_executions: [{ name: 'leave_balance', status: 'ok', success: true }],
    memory_accesses: [{ store: 'short_term', operation: 'read' }],
    decision: { outcome: 'approve_with_conditions' },
    actions: [],
    pending_actions: [],
    errors: [],
    approval_checkpoint: { status: 'awaiting' },
  },
  metrics: {
    duration_ms: 1200,
    agent_count: 6,
    tool_count: 2,
    tool_success_rate: 1,
    retry_count: 0,
    action_count: 1,
    action_success_rate: 0,
    validation_failed: false,
    human_approval_required: true,
    decision_confidence: 0.86,
    escalated: false,
    workflow_type: 'leave_attendance',
    organization_id: 'demo-org',
    status: 'awaiting_human_approval',
    success: false,
  },
  router_status: 'matched',
  request_id: 'req-1',
}

function authenticatedFetch(user = demoUsers.manager) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = (init?.method || 'GET').toUpperCase()

    if (url.includes('/auth/me')) return jsonResponse(user)
    if (url.includes('/workflows/types')) {
      return jsonResponse({
        workflows: [
          {
            workflow_type: 'leave_attendance',
            name: 'Leave',
            description: '',
            version: '1.0',
          },
        ],
      })
    }
    if (url.includes('/workflows/wf-001/approve') && method === 'POST') {
      return jsonResponse({
        ...sampleWorkflow,
        status: 'completed',
        approval_status: 'approved',
      })
    }
    if (url.includes('/workflows/wf-001/reject') && method === 'POST') {
      return jsonResponse({
        ...sampleWorkflow,
        status: 'rejected',
        approval_status: 'rejected',
      })
    }
    if (url.includes('/workflows/run') && method === 'POST') {
      return jsonResponse({
        ...sampleWorkflow,
        status: 'needs_clarification',
        workflow_type: 'leave_attendance',
        response: 'What dates would you like to request leave for?',
        understanding: {
          intent: 'leave_request',
          workflow_type: 'leave_attendance',
          request_kind: 'action',
          summary_label: 'Leave request',
          needs_clarification: true,
          clarification_question: 'What dates would you like to request leave for?',
          confidence: 0.8,
          entities: {},
        },
      })
    }
    if (url.includes('/workflows/wf-001')) return jsonResponse(sampleWorkflow)
    if (url.includes('status=awaiting_human_approval')) {
      return jsonResponse({
        workflows: [sampleSummary],
        total: 1,
        limit: 100,
        offset: 0,
      })
    }
    if (url.includes('/workflows')) {
      return jsonResponse({
        workflows: [sampleSummary],
        total: 1,
        limit: 20,
        offset: 0,
      })
    }
    return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404)
  })
}

describe('workflows and approvals UI', () => {
  beforeEach(() => {
    setStoredToken('token')
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setStoredToken(null)
  })

  it('renders workflow list', async () => {
    vi.stubGlobal('fetch', authenticatedFetch())
    renderWithProviders(<App />, { route: '/workflows', token: 'token' })
    expect(
      await screen.findByRole('heading', { name: /^workflows$/i }, { timeout: 8000 }),
    ).toBeInTheDocument()
    expect(await screen.findByText(/leave & attendance/i)).toBeInTheDocument()
    expect(screen.getByText(/wf-001/i)).toBeInTheDocument()
  }, 15000)

  it('renders workflow detail with timeline and decision', async () => {
    vi.stubGlobal('fetch', authenticatedFetch())
    renderWithProviders(<App />, { route: '/workflows/wf-001', token: 'token' })
    expect(await screen.findByText(/agentic pipeline/i)).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: /^decision$/i }).length).toBeGreaterThan(0)
    expect(screen.getByText(/within policy/i)).toBeInTheDocument()
    expect(screen.getByText(/run metrics/i)).toBeInTheDocument()
  })

  it('supports approval actions', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', authenticatedFetch())
    renderWithProviders(<App />, { route: '/approvals', token: 'token' })
    expect(await screen.findByRole('heading', { name: /approval center/i })).toBeInTheDocument()
    const approveBtn = await screen.findByRole('button', { name: /^approve$/i })
    await user.click(approveBtn)
    await user.click(await screen.findByRole('button', { name: /confirm/i }))
    await waitFor(() => {
      expect(screen.getByText(/approval completed/i)).toBeInTheDocument()
    })
  })

  it('shows loading then empty states on dashboard', async () => {
    let resolveWorkflows: ((value: Response) => void) | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/auth/me')) return jsonResponse(demoUsers.employee)
        return await new Promise<Response>((resolve) => {
          resolveWorkflows = resolve
        })
      }),
    )
    renderWithProviders(<App />, { route: '/dashboard', token: 'token' })
    expect(await screen.findByText(/loading dashboard/i)).toBeInTheDocument()
    resolveWorkflows?.(jsonResponse({ workflows: [], total: 0, limit: 200, offset: 0 }))
    expect(
      await screen.findByText(/no workflows found/i, {}, { timeout: 8000 }),
    ).toBeInTheDocument()
  }, 15000)

  it('renders natural-language request input and clarification', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', authenticatedFetch(demoUsers.employee))
    renderWithProviders(<App />, { route: '/requests', token: 'token' })
    expect(
      await screen.findByLabelText(/describe what you need/i),
    ).toBeInTheDocument()
    await user.type(
      screen.getByLabelText(/describe what you need/i),
      'I need leave',
    )
    await user.click(screen.getByRole('button', { name: /run request/i }))
    expect(await screen.findByText(/clarification needed/i)).toBeInTheDocument()
    expect(
      screen.getAllByText(/what dates would you like to request leave for/i).length,
    ).toBeGreaterThan(0)
    expect(screen.getByText(/request understood as/i)).toBeInTheDocument()
  })

  it('shows error state with retry', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/auth/me')) return jsonResponse(demoUsers.hr)
        return jsonResponse(
          { error: { code: 'DATABASE_UNAVAILABLE', message: 'Database down' } },
          503,
        )
      }),
    )
    renderWithProviders(<App />, { route: '/workflows', token: 'token' })
    expect(
      await screen.findByText(/could not load workflows/i, {}, { timeout: 8000 }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
