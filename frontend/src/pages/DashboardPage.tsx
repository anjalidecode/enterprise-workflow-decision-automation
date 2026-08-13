import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { workflowsApi } from '../api'
import { ApiClientError } from '../api/client'
import { Button, LoadingBlock, StatePanel, StatusBadge } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import type { WorkflowSummary } from '../types/api'
import {
  formatDateTime,
  shortId,
  workflowTypeLabel,
} from '../utils/format'
import { canApprove, roleLabel } from '../utils/rbac'

export function DashboardPage() {
  const { user } = useAuth()
  const [items, setItems] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await workflowsApi.list({ limit: 200, offset: 0 })
      setItems(res.workflows)
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to load dashboard.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const stats = useMemo(() => {
    const total = items.length
    const completed = items.filter((w) => (w.status || '').includes('complet')).length
    const pending = items.filter(
      (w) =>
        w.status === 'awaiting_human_approval' || w.approval_status === 'awaiting',
    ).length
    const rejected = items.filter(
      (w) =>
        (w.status || '').includes('reject') ||
        (w.outcome || '').toLowerCase().includes('reject'),
    ).length
    const activeTypes = new Set(items.map((w) => w.workflow_type).filter(Boolean)).size

    const distribution = new Map<string, number>()
    for (const w of items) {
      const key = w.workflow_type || 'unknown'
      distribution.set(key, (distribution.get(key) || 0) + 1)
    }
    const distRows = [...distribution.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)

    const recent = [...items]
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
      .slice(0, 8)

    const attention = items.filter(
      (w) =>
        w.status === 'awaiting_human_approval' ||
        w.approval_status === 'awaiting' ||
        (w.status || '').includes('fail') ||
        (w.status || '').includes('error'),
    )

    return { total, completed, pending, rejected, activeTypes, distRows, recent, attention }
  }, [items])

  if (loading) return <LoadingBlock label="Loading dashboard…" />
  if (error) {
    return (
      <StatePanel
        variant="error"
        title="Dashboard unavailable"
        message={error}
        action={
          <Button variant="primary" onClick={() => void load()}>
            Retry
          </Button>
        }
      />
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <span>Home</span>
            <span>/</span>
            <span>Dashboard</span>
          </div>
          <h1>
            {user?.role === 'employee'
              ? 'My dashboard'
              : user?.role === 'hr'
                ? 'HR dashboard'
                : 'Operations dashboard'}
          </h1>
          <p>
            Signed in as {user?.username} ({roleLabel(user?.role || 'employee')}) ·{' '}
            {user?.organization_id}. Metrics below are computed from workflow runs returned
            by the API — no invented statistics.
          </p>
        </div>
        <Button variant="primary" onClick={() => void load()}>
          Refresh
        </Button>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label">Total workflows</div>
          <div className="value">{stats.total}</div>
        </div>
        <div className="stat-card">
          <div className="label">Completed</div>
          <div className="value">{stats.completed}</div>
        </div>
        <div className="stat-card">
          <div className="label">Pending approvals</div>
          <div className="value">{stats.pending}</div>
          <div className="hint">
            {canApprove(user?.role || 'employee')
              ? 'Visible to approver roles'
              : 'Shown from your visible runs'}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Rejected</div>
          <div className="value">{stats.rejected}</div>
        </div>
        <div className="stat-card">
          <div className="label">Active HR processes</div>
          <div className="value">{stats.activeTypes}</div>
          <div className="hint">Distinct workflow types</div>
        </div>
      </div>

      <div className="panel-grid">
        <div className="card">
          <div className="card-header">
            <h2>Recent workflow activity</h2>
            <Link to="/workflows">View all</Link>
          </div>
          {stats.recent.length === 0 ? (
            <div className="card-body muted">No workflows found.</div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent.map((w) => (
                    <tr key={w.workflow_id}>
                      <td>
                        <Link className="mono" to={`/workflows/${w.workflow_id}`}>
                          {shortId(w.workflow_id)}
                        </Link>
                      </td>
                      <td>{workflowTypeLabel(w.workflow_type)}</td>
                      <td>
                        <StatusBadge status={w.status} />
                      </td>
                      <td>{w.outcome || '—'}</td>
                      <td>{formatDateTime(w.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="stack-md">
          <div className="card">
            <div className="card-header">
              <h2>Workflow distribution</h2>
            </div>
            <div className="card-body">
              {stats.distRows.length === 0 ? (
                <p className="muted">No distribution data yet.</p>
              ) : (
                <div className="dist-bar">
                  {stats.distRows.map(([type, count]) => (
                    <div className="dist-row" key={type}>
                      <span>{workflowTypeLabel(type)}</span>
                      <div className="dist-track" aria-hidden>
                        <div
                          className="dist-fill"
                          style={{
                            width: `${Math.max(8, (count / Math.max(stats.total, 1)) * 100)}%`,
                          }}
                        />
                      </div>
                      <strong>{count}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2>Needs attention</h2>
              {canApprove(user?.role || 'employee') ? (
                <Link to="/approvals">Approvals</Link>
              ) : null}
            </div>
            <div className="card-body stack-sm">
              {stats.attention.length === 0 ? (
                <p className="muted">No alerts from visible workflow runs.</p>
              ) : (
                stats.attention.slice(0, 6).map((w) => (
                  <div key={w.workflow_id} className="split" style={{ justifyContent: 'space-between' }}>
                    <div>
                      <Link className="mono" to={`/workflows/${w.workflow_id}`}>
                        {shortId(w.workflow_id, 10)}
                      </Link>
                      <div className="muted" style={{ fontSize: '0.8rem' }}>
                        {workflowTypeLabel(w.workflow_type)}
                      </div>
                    </div>
                    <StatusBadge status={w.status} />
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
