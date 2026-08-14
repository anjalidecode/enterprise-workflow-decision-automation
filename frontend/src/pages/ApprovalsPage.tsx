import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { workflowsApi } from '../api'
import { ApiClientError } from '../api/client'
import { Button, LoadingBlock, Modal, StatePanel, StatusBadge } from '../components/ui/Primitives'
import { useToast } from '../context/ToastContext'
import type { WorkflowSummary } from '../types/api'
import { formatDateTime, shortId, workflowTypeLabel } from '../utils/format'

export function ApprovalsPage() {
  const { notify } = useToast()
  const [items, setItems] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<WorkflowSummary | null>(null)
  const [mode, setMode] = useState<'approve' | 'reject' | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await workflowsApi.list({
        status: 'awaiting_human_approval',
        limit: 100,
      })
      setItems(res.workflows)
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to load approvals.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function submit() {
    if (!selected || !mode) return
    setBusy(true)
    try {
      const updated =
        mode === 'approve'
          ? await workflowsApi.approve(selected.workflow_id, { reason })
          : await workflowsApi.reject(selected.workflow_id, { reason })
      notify({
        tone: mode === 'approve' ? 'success' : 'warning',
        title: mode === 'approve' ? 'Approval completed' : 'Workflow rejected',
        message: `${updated.workflow_id} → ${updated.status}`,
      })
      setSelected(null)
      setMode(null)
      setReason('')
      await load()
    } catch (err) {
      notify({
        tone: 'danger',
        title: 'Action failed',
        message: err instanceof ApiClientError ? err.message : 'Request failed.',
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <span>Approvals</span>
          </div>
          <h1>Approval center</h1>
          <p>
            Workflows paused for human approval. Actions call the backend resume API —
            approval logic is not implemented in the frontend.
          </p>
        </div>
        <Button variant="primary" onClick={() => void load()} disabled={loading}>
          Refresh
        </Button>
      </div>

      {loading ? <LoadingBlock label="Loading approvals…" /> : null}
      {!loading && error ? (
        <StatePanel
          variant="error"
          title="Approvals unavailable"
          message={error}
          action={
            <Button variant="primary" onClick={() => void load()}>
              Retry
            </Button>
          }
        />
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <StatePanel
          title="No workflows awaiting approval"
          message="When a decision requires human review, it will appear here."
        />
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <div className="stack-md">
          {items.map((item) => (
            <div className="card" key={item.workflow_id}>
              <div className="card-body">
                <div className="split" style={{ justifyContent: 'space-between' }}>
                  <div>
                    <div className="muted" style={{ fontSize: '0.8rem' }}>
                      {workflowTypeLabel(item.workflow_type)}
                    </div>
                    <Link className="mono" to={`/workflows/${item.workflow_id}`}>
                      {item.workflow_id}
                    </Link>
                    <div className="muted" style={{ marginTop: '0.35rem', fontSize: '0.85rem' }}>
                      Requested {formatDateTime(item.created_at)}
                    </div>
                  </div>
                  <StatusBadge status={item.status} />
                </div>
                <div className="split" style={{ marginTop: '0.85rem' }}>
                  <span className="badge">Decision: {item.outcome || '—'}</span>
                  <span className="badge">
                    Approval: {item.approval_status || 'awaiting'}
                  </span>
                  <span className="muted">Org: {item.organization_id}</span>
                </div>
                <div className="split" style={{ marginTop: '1rem' }}>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      setSelected(item)
                      setMode('approve')
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      setSelected(item)
                      setMode('reject')
                    }}
                  >
                    Reject
                  </Button>
                  <Link to={`/workflows/${item.workflow_id}`}>
                    <Button size="sm">Review detail</Button>
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <Modal
        open={Boolean(selected && mode)}
        title={mode === 'approve' ? 'Approve workflow' : 'Reject workflow'}
        onClose={() => {
          if (!busy) {
            setSelected(null)
            setMode(null)
          }
        }}
        actions={
          <>
            <Button disabled={busy} onClick={() => setSelected(null)}>
              Cancel
            </Button>
            <Button
              variant={mode === 'approve' ? 'primary' : 'danger'}
              disabled={busy}
              onClick={() => void submit()}
            >
              {busy ? 'Submitting…' : 'Confirm'}
            </Button>
          </>
        }
      >
        <p className="muted" style={{ marginBottom: '0.75rem' }}>
          Workflow <span className="mono">{shortId(selected?.workflow_id || '', 16)}</span>
        </p>
        <div className="form-row">
          <label htmlFor="reason">Reason</label>
          <textarea
            id="reason"
            className="textarea"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy}
          />
        </div>
      </Modal>
    </div>
  )
}
