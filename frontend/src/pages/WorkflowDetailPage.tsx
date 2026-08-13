import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { workflowsApi } from '../api'
import { ApiClientError } from '../api/client'
import {
  AuditSummary,
  DecisionPanel,
  MetricsPanel,
  WorkflowTimeline,
} from '../components/workflow/WorkflowPanels'
import { Button, LoadingBlock, Modal, StatePanel, StatusBadge } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import type { Workflow } from '../types/api'
import {
  formatDateTime,
  titleCaseStatus,
  workflowTypeLabel,
} from '../utils/format'
import { canApprove } from '../utils/rbac'

export function WorkflowDetailPage() {
  const { workflowId = '' } = useParams()
  const { user } = useAuth()
  const { notify } = useToast()
  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [modal, setModal] = useState<'approve' | 'reject' | null>(null)
  const [reason, setReason] = useState('')

  async function load() {
    if (!workflowId) return
    setLoading(true)
    setError(null)
    try {
      const data = await workflowsApi.get(workflowId)
      setWorkflow(data)
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to load workflow.')
      setWorkflow(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [workflowId])

  async function submitDecision(approved: boolean) {
    if (!workflow) return
    setActionLoading(true)
    try {
      const updated = approved
        ? await workflowsApi.approve(workflow.workflow_id, { reason })
        : await workflowsApi.reject(workflow.workflow_id, { reason })
      setWorkflow(updated)
      setModal(null)
      setReason('')
      notify({
        tone: approved ? 'success' : 'warning',
        title: approved ? 'Approval completed' : 'Workflow rejected',
        message: `Workflow ${updated.workflow_id} is now ${updated.status}.`,
      })
    } catch (err) {
      notify({
        tone: 'danger',
        title: 'Action failed',
        message: err instanceof ApiClientError ? err.message : 'Approval action failed.',
      })
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <LoadingBlock label="Loading workflow detail…" />
  if (error || !workflow) {
    return (
      <StatePanel
        variant="error"
        title="Workflow not available"
        message={error || 'Not found.'}
        action={
          <Button variant="primary" onClick={() => void load()}>
            Retry
          </Button>
        }
      />
    )
  }

  const awaiting =
    workflow.status === 'awaiting_human_approval' ||
    workflow.approval_status === 'awaiting'
  const showApprove = awaiting && user && canApprove(user.role)
  const audit = workflow.audit
  const agents = audit?.agents || []
  const tools = audit?.tool_executions || []
  const memory = audit?.memory_accesses || []

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <Link to="/workflows">Workflows</Link>
            <span>/</span>
            <span className="mono">{workflow.workflow_id}</span>
          </div>
          <h1>{workflowTypeLabel(workflow.workflow_type)}</h1>
          <p>
            Agentic workflow run with specialized agents, tools, policy, memory, decision,
            and human approval checkpoints.
          </p>
        </div>
        <div className="split">
          <StatusBadge status={workflow.status} />
          <Button onClick={() => void load()}>Refresh</Button>
          {showApprove ? (
            <>
              <Button variant="primary" onClick={() => setModal('approve')}>
                Approve
              </Button>
              <Button variant="danger" onClick={() => setModal('reject')}>
                Reject
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label">Status</div>
          <div className="value" style={{ fontSize: '1.2rem' }}>
            {titleCaseStatus(workflow.status)}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Current stage</div>
          <div className="value" style={{ fontSize: '1.2rem' }}>
            {titleCaseStatus(workflow.current_stage || '—')}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Approval</div>
          <div className="value" style={{ fontSize: '1.2rem' }}>
            {titleCaseStatus(workflow.approval_status || 'n/a')}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Organization</div>
          <div className="value" style={{ fontSize: '1.2rem' }}>
            {workflow.organization_id || '—'}
          </div>
        </div>
      </div>

      <div className="panel-grid" style={{ marginBottom: '1rem' }}>
        <div className="card">
          <div className="card-header">
            <h2>Agentic pipeline</h2>
          </div>
          <div className="card-body">
            <WorkflowTimeline workflow={workflow} audit={audit} />
          </div>
        </div>
        <div className="stack-md">
          <DecisionPanel workflow={workflow} />
          <div className="card">
            <div className="card-header">
              <h3>Final response</h3>
            </div>
            <div className="card-body">
              <p>{workflow.response || 'No final response yet.'}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="panel-grid" style={{ marginBottom: '1rem' }}>
        <div className="card">
          <div className="card-header">
            <h2>Agents executed</h2>
            <span className="badge">{agents.length}</span>
          </div>
          <div className="card-body">
            {agents.length === 0 ? (
              <p className="muted">No agent records in audit snapshot.</p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Agent</th>
                      <th>Status</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((agent, index) => (
                      <tr key={`${String(agent.name || index)}-${index}`}>
                        <td>{String(agent.order ?? agent.sequence ?? index + 1)}</td>
                        <td>
                          {String(agent.name || agent.agent || agent.agent_name || 'Agent')}
                        </td>
                        <td>
                          <StatusBadge status={String(agent.status || 'executed')} />
                        </td>
                        <td className="muted">
                          {String(agent.summary || agent.message || agent.role || '—')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="stack-md">
          <MetricsPanel metrics={workflow.metrics} />
          <AuditSummary audit={audit} />
        </div>
      </div>

      <div className="panel-grid">
        <div className="card">
          <div className="card-header">
            <h2>Tool executions</h2>
            <span className="badge">{tools.length}</span>
          </div>
          <div className="card-body">
            {tools.length === 0 ? (
              <p className="muted">No tool executions recorded.</p>
            ) : (
              <ul className="stack-sm">
                {tools.map((tool, index) => (
                  <li key={index}>
                    <strong>
                      {String(tool.name || tool.tool || tool.tool_name || `Tool ${index + 1}`)}
                    </strong>
                    <div className="muted" style={{ fontSize: '0.85rem' }}>
                      {String(tool.status || '')}{' '}
                      {tool.success != null ? (tool.success ? '· success' : '· failed') : ''}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Memory accesses</h2>
            <span className="badge">{memory.length}</span>
          </div>
          <div className="card-body">
            {memory.length === 0 ? (
              <p className="muted">No memory access records.</p>
            ) : (
              <ul className="stack-sm">
                {memory.map((item, index) => (
                  <li key={index}>
                    <strong>
                      {String(item.store || item.type || item.memory_type || 'Memory')}
                    </strong>
                    <div className="muted" style={{ fontSize: '0.85rem' }}>
                      {String(item.operation || item.action || item.key || 'access')}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: '1rem' }}>
        <div className="card-header">
          <h2>Actions & audit timestamps</h2>
        </div>
        <div className="card-body panel-grid">
          <div>
            <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Completed actions</h3>
            {workflow.actions.length === 0 ? (
              <p className="muted">None</p>
            ) : (
              <ul>
                {workflow.actions.map((action, index) => (
                  <li key={index}>{JSON.stringify(action)}</li>
                ))}
              </ul>
            )}
            <h3 style={{ fontSize: '0.95rem', margin: '0.75rem 0 0.5rem' }}>
              Pending actions
            </h3>
            {workflow.pending_actions.length === 0 ? (
              <p className="muted">None</p>
            ) : (
              <ul>
                {workflow.pending_actions.map((action, index) => (
                  <li key={index}>{JSON.stringify(action)}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="stack-sm">
            <div className="metric-row">
              <span className="muted">Started</span>
              <strong>{formatDateTime(audit?.started_at)}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Completed</span>
              <strong>{formatDateTime(audit?.completed_at)}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Request ID</span>
              <strong className="mono">{workflow.request_id || '—'}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Router</span>
              <strong>{workflow.router_status || '—'}</strong>
            </div>
          </div>
        </div>
      </div>

      <Modal
        open={modal !== null}
        title={modal === 'approve' ? 'Approve workflow' : 'Reject workflow'}
        onClose={() => {
          if (!actionLoading) setModal(null)
        }}
        actions={
          <>
            <Button disabled={actionLoading} onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button
              variant={modal === 'approve' ? 'primary' : 'danger'}
              disabled={actionLoading}
              onClick={() => void submitDecision(modal === 'approve')}
            >
              {actionLoading
                ? 'Submitting…'
                : modal === 'approve'
                  ? 'Confirm approve'
                  : 'Confirm reject'}
            </Button>
          </>
        }
      >
        <p className="muted" style={{ marginBottom: '0.75rem' }}>
          This calls the backend approval API. The WorkflowEngine remains authoritative.
        </p>
        <div className="form-row">
          <label htmlFor="approval-reason">Reason (optional)</label>
          <textarea
            id="approval-reason"
            className="textarea"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={actionLoading}
          />
        </div>
      </Modal>
    </div>
  )
}
