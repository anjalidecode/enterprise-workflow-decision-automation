import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { workflowsApi } from '../api'
import { ApiClientError } from '../api/client'
import { Button, LoadingBlock, StatePanel, StatusBadge } from '../components/ui/Primitives'
import type { Workflow, WorkflowSummary } from '../types/api'
import {
  formatDateTime,
  shortId,
  titleCaseStatus,
  workflowTypeLabel,
} from '../utils/format'

type AuditRow = {
  summary: WorkflowSummary
  detail: Workflow | null
  error?: string
}

export function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const list = await workflowsApi.list({ limit: 25, offset: 0 })
      const details = await Promise.all(
        list.workflows.map(async (summary) => {
          try {
            const detail = await workflowsApi.get(summary.workflow_id)
            return { summary, detail } satisfies AuditRow
          } catch (err) {
            return {
              summary,
              detail: null,
              error: err instanceof ApiClientError ? err.message : 'Detail unavailable',
            } satisfies AuditRow
          }
        }),
      )
      setRows(details)
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to load audit data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <span>Audit</span>
          </div>
          <h1>Audit trail</h1>
          <p>
            Audit snapshots from workflow runs: agents, tools, memory, decisions, actions,
            and timestamps.
          </p>
        </div>
        <Button variant="primary" onClick={() => void load()} disabled={loading}>
          Refresh
        </Button>
      </div>

      {loading ? <LoadingBlock label="Loading audit records…" /> : null}
      {!loading && error ? (
        <StatePanel
          variant="error"
          title="Audit unavailable"
          message={error}
          action={
            <Button variant="primary" onClick={() => void load()}>
              Retry
            </Button>
          }
        />
      ) : null}
      {!loading && !error && rows.length === 0 ? (
        <StatePanel title="No audit records" message="Run workflows to populate audit snapshots." />
      ) : null}

      {!loading && !error && rows.length > 0 ? (
        <div className="card">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Workflow</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Decision</th>
                  <th>Agents</th>
                  <th>Tools</th>
                  <th>Memory</th>
                  <th>Actions</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ summary, detail, error: rowError }) => {
                  const audit = detail?.audit
                  return (
                    <tr key={summary.workflow_id}>
                      <td>
                        <Link className="mono" to={`/workflows/${summary.workflow_id}`}>
                          {shortId(summary.workflow_id, 10)}
                        </Link>
                      </td>
                      <td>{workflowTypeLabel(summary.workflow_type)}</td>
                      <td>
                        <StatusBadge status={summary.status} />
                      </td>
                      <td>
                        {rowError
                          ? rowError
                          : titleCaseStatus(
                              String(
                                audit?.final_outcome ||
                                  detail?.decision?.outcome ||
                                  summary.outcome ||
                                  '—',
                              ),
                            )}
                      </td>
                      <td>{audit?.agents.length ?? '—'}</td>
                      <td>{audit?.tool_executions.length ?? '—'}</td>
                      <td>{audit?.memory_accesses.length ?? '—'}</td>
                      <td>{audit?.actions.length ?? '—'}</td>
                      <td>{formatDateTime(audit?.started_at || summary.created_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  )
}
