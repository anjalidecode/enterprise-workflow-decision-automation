import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { workflowsApi } from '../api'
import { ApiClientError } from '../api/client'
import { Button, LoadingBlock, StatePanel } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import type { WorkflowSummary } from '../types/api'
import { formatDurationMs } from '../utils/format'
import { canApprove, canRunWorkflowType } from '../utils/rbac'

export function AnalyticsPage() {
  const { user } = useAuth()
  const [items, setItems] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [durations, setDurations] = useState<number[]>([])
  const [agentCounts, setAgentCounts] = useState<number[]>([])
  const [toolCounts, setToolCounts] = useState<number[]>([])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const list = await workflowsApi.list({ limit: 50, offset: 0 })
      setItems(list.workflows)
      const sample = list.workflows.slice(0, 12)
      const details = await Promise.all(
        sample.map(async (row) => {
          try {
            return await workflowsApi.get(row.workflow_id)
          } catch {
            return null
          }
        }),
      )
      setDurations(
        details
          .map((d) => d?.metrics?.duration_ms)
          .filter((v): v is number => typeof v === 'number'),
      )
      setAgentCounts(
        details
          .map((d) => d?.metrics?.agent_count)
          .filter((v): v is number => typeof v === 'number'),
      )
      setToolCounts(
        details
          .map((d) => d?.metrics?.tool_count)
          .filter((v): v is number => typeof v === 'number'),
      )
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Unable to load analytics.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const stats = useMemo(() => {
    const completed = items.filter((w) => (w.status || '').includes('complet')).length
    const pending = items.filter(
      (w) => w.status === 'awaiting_human_approval' || w.approval_status === 'awaiting',
    ).length
    const rejected = items.filter((w) => (w.status || '').includes('reject')).length
    const avg = (values: number[]) =>
      values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
    return {
      total: items.length,
      completed,
      pending,
      rejected,
      avgDuration: avg(durations),
      avgAgents: avg(agentCounts),
      avgTools: avg(toolCounts),
    }
  }, [items, durations, agentCounts, toolCounts])

  if (loading) return <LoadingBlock label="Loading analytics…" />
  if (error) {
    return (
      <StatePanel
        variant="error"
        title="Unable to load analytics"
        message={error}
        action={
          <Button variant="primary" onClick={() => void load()}>
            Retry
          </Button>
        }
      />
    )
  }

  if (items.length === 0) {
    return (
      <div>
        <div className="page-header">
          <div>
            <div className="breadcrumbs">
              <Link to="/dashboard">Home</Link>
              <span>/</span>
              <span>Analytics</span>
            </div>
            <h1>Analytics</h1>
            <p>Operational metrics computed from workflow runs you are authorized to view.</p>
          </div>
        </div>
        <StatePanel
          title="No analytics available yet"
          message="Run workflows to populate completion, approval, duration, and agent metrics."
        />
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <span>Analytics</span>
          </div>
          <h1>Analytics</h1>
          <p>
            Counts and averages from persisted workflow runs
            {user?.organization_id ? ` for ${user.organization_id}` : ''}. No estimated or
            synthetic values are shown.
          </p>
        </div>
        <Button variant="primary" onClick={() => void load()}>
          Refresh
        </Button>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label">Workflows</div>
          <div className="value">{stats.total}</div>
        </div>
        <div className="stat-card">
          <div className="label">Completed</div>
          <div className="value">{stats.completed}</div>
        </div>
        <div className="stat-card">
          <div className="label">Pending approvals</div>
          <div className="value">{stats.pending}</div>
        </div>
        <div className="stat-card">
          <div className="label">Rejected</div>
          <div className="value">{stats.rejected}</div>
        </div>
        <div className="stat-card">
          <div className="label">Avg. duration</div>
          <div className="value" style={{ fontSize: '1.25rem' }}>
            {stats.avgDuration == null ? '—' : formatDurationMs(stats.avgDuration)}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Avg. agents / tools</div>
          <div className="value" style={{ fontSize: '1.25rem' }}>
            {stats.avgAgents == null ? '—' : stats.avgAgents.toFixed(1)} /{' '}
            {stats.avgTools == null ? '—' : stats.avgTools.toFixed(1)}
          </div>
        </div>
      </div>

      {canApprove(user?.role || 'employee') && canRunWorkflowType(user?.role || 'employee', 'leave_attendance') ? (
        <p className="muted">Metrics include only runs visible to your role.</p>
      ) : null}
    </div>
  )
}
