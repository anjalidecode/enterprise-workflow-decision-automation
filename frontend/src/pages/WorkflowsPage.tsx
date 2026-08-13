import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { workflowsApi } from '../api'
import { ApiClientError } from '../api/client'
import { Button, LoadingBlock, StatePanel, StatusBadge } from '../components/ui/Primitives'
import type { WorkflowSummary, WorkflowTypeItem } from '../types/api'
import {
  formatDateTime,
  shortId,
  workflowTypeLabel,
} from '../utils/format'

const PAGE_SIZE = 20

export function WorkflowsPage() {
  const [items, setItems] = useState<WorkflowSummary[]>([])
  const [total, setTotal] = useState(0)
  const [types, setTypes] = useState<WorkflowTypeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [workflowType, setWorkflowType] = useState('')
  const [offset, setOffset] = useState(0)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [list, typeRes] = await Promise.all([
        workflowsApi.list({
          status: status || undefined,
          workflow_type: workflowType || undefined,
          limit: PAGE_SIZE,
          offset,
        }),
        workflowsApi.listTypes(),
      ])
      setItems(list.workflows)
      setTotal(list.total)
      setTypes(typeRes.workflows)
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to load workflows.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [status, workflowType, offset])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return items
    return items.filter(
      (w) =>
        w.workflow_id.toLowerCase().includes(q) ||
        w.workflow_type.toLowerCase().includes(q) ||
        (w.outcome || '').toLowerCase().includes(q) ||
        (w.status || '').toLowerCase().includes(q),
    )
  }, [items, search])

  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <span>Workflows</span>
          </div>
          <h1>Workflows</h1>
          <p>
            Persisted workflow runs for your organization, filtered by role ownership rules
            on the backend.
          </p>
        </div>
        <Button variant="primary" onClick={() => void load()} disabled={loading}>
          Refresh
        </Button>
      </div>

      <div className="filters">
        <input
          className="input"
          placeholder="Search ID, type, status…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search workflows"
        />
        <select
          className="select"
          value={status}
          onChange={(e) => {
            setOffset(0)
            setStatus(e.target.value)
          }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="completed">completed</option>
          <option value="awaiting_human_approval">awaiting_human_approval</option>
          <option value="rejected">rejected</option>
          <option value="failed">failed</option>
        </select>
        <select
          className="select"
          value={workflowType}
          onChange={(e) => {
            setOffset(0)
            setWorkflowType(e.target.value)
          }}
          aria-label="Filter by workflow type"
        >
          <option value="">All types</option>
          {types.map((t) => (
            <option key={t.workflow_type} value={t.workflow_type}>
              {t.name || workflowTypeLabel(t.workflow_type)}
            </option>
          ))}
        </select>
      </div>

      {loading ? <LoadingBlock label="Loading workflows…" /> : null}
      {!loading && error ? (
        <StatePanel
          variant="error"
          title="Could not load workflows"
          message={error}
          action={
            <Button variant="primary" onClick={() => void load()}>
              Retry
            </Button>
          }
        />
      ) : null}
      {!loading && !error && filtered.length === 0 ? (
        <StatePanel title="No workflows found." message="Try adjusting filters or run a new workflow from a domain page." />
      ) : null}

      {!loading && !error && filtered.length > 0 ? (
        <div className="card">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Workflow ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Outcome</th>
                  <th>Approval</th>
                  <th>Organization</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((w) => (
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
                    <td>
                      {w.approval_status ? (
                        <StatusBadge status={w.approval_status} />
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>{w.organization_id || '—'}</td>
                    <td>{formatDateTime(w.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div
            className="card-body split"
            style={{ justifyContent: 'space-between', borderTop: '1px solid var(--border)' }}
          >
            <span className="muted">
              Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              {search ? ' (filtered on this page)' : ''}
            </span>
            <div className="split">
              <Button
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((v) => Math.max(0, v - PAGE_SIZE))}
              >
                Previous
              </Button>
              <span className="muted">
                Page {page} / {pageCount}
              </span>
              <Button
                size="sm"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset((v) => v + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
