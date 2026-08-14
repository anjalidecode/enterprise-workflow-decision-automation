import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { workflowsApi } from '../api'
import { ApiClientError } from '../api/client'
import { Button, LoadingBlock, StatePanel, StatusBadge } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import type { WorkflowSummary } from '../types/api'
import { formatDateTime, shortId, workflowTypeLabel } from '../utils/format'

/**
 * There is no GET /employees endpoint in the current API.
 * HR sees organization workflow activity as a proxy for workforce operations;
 * employees see a self-service profile derived from /auth/me.
 */
export function EmployeesPage() {
  const { user } = useAuth()
  const [items, setItems] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await workflowsApi.list({ limit: 100 })
      setItems(res.workflows)
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to load employee view.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const activity = useMemo(() => items.slice(0, 12), [items])

  if (user?.role === 'employee') {
    return (
      <div>
        <div className="page-header">
          <div>
            <div className="breadcrumbs">
              <Link to="/dashboard">Home</Link>
              <span>/</span>
              <span>My profile</span>
            </div>
            <h1>My employee profile</h1>
            <p>Self-service view from authenticated identity. Organization-wide employee directories are not exposed to employees.</p>
          </div>
        </div>
        <div className="card card-body stack-sm">
          <div className="metric-row">
            <span className="muted">Username</span>
            <strong>{user.username}</strong>
          </div>
          <div className="metric-row">
            <span className="muted">User ID</span>
            <strong className="mono">{user.user_id}</strong>
          </div>
          <div className="metric-row">
            <span className="muted">Employee ID</span>
            <strong>{user.employee_id || '—'}</strong>
          </div>
          <div className="metric-row">
            <span className="muted">Organization</span>
            <strong>{user.organization_id}</strong>
          </div>
          <div className="metric-row">
            <span className="muted">Role</span>
            <strong>{user.role}</strong>
          </div>
        </div>
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
            <span>Employees</span>
          </div>
          <h1>Employees</h1>
          <p>
            Workforce activity from workflow records your role is allowed to view. A
            dedicated employee directory is not exposed by the current API.
          </p>
        </div>
        <Button variant="primary" onClick={() => void load()} disabled={loading}>
          Refresh
        </Button>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="card-header">
          <h2>Directory</h2>
        </div>
        <div className="card-body muted">
          Employee name, department, and employment status are not returned by the
          current API. Recent workflow activity is shown instead of a synthetic roster.
        </div>
      </div>

      {loading ? <LoadingBlock label="Loading activity…" /> : null}
      {!loading && error ? (
        <StatePanel
          variant="error"
          title="Unable to load activity"
          message={error}
          action={
            <Button variant="primary" onClick={() => void load()}>
              Retry
            </Button>
          }
        />
      ) : null}
      {!loading && !error ? (
        <div className="card">
          <div className="card-header">
            <h2>Recent workforce-related workflow activity</h2>
          </div>
          {activity.length === 0 ? (
            <div className="card-body muted">No workflow activity found.</div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Workflow</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.map((w) => (
                    <tr key={w.workflow_id}>
                      <td>
                        <Link className="mono" to={`/workflows/${w.workflow_id}`}>
                          {shortId(w.workflow_id, 12)}
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
      ) : null}
    </div>
  )
}
