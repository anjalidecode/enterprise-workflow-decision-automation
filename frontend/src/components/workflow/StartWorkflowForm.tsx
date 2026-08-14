import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { workflowsApi } from '../../api'
import { ApiClientError } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import type { Workflow, WorkflowTypeItem } from '../../types/api'
import { canRunWorkflowType } from '../../utils/rbac'
import { workflowTypeLabel } from '../../utils/format'
import { Button } from '../ui/Primitives'
import { WorkflowResultBanner } from './WorkflowPanels'

type Props = {
  defaultWorkflowType?: string
  title?: string
  description?: string
  placeholder?: string
  lockedType?: boolean
}

export function StartWorkflowForm({
  defaultWorkflowType,
  title = 'Start workflow',
  description = 'Submit a structured HR request. Specialized agents execute the workflow — this is not a chat interface.',
  placeholder = 'Describe the HR request…',
  lockedType = false,
}: Props) {
  const { user } = useAuth()
  const { notify } = useToast()
  const navigate = useNavigate()
  const [types, setTypes] = useState<WorkflowTypeItem[]>([])
  const [workflowType, setWorkflowType] = useState(defaultWorkflowType || '')
  const [request, setRequest] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<Workflow | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    workflowsApi
      .listTypes()
      .then((res) => {
        if (cancelled) return
        const role = user?.role || 'employee'
        const allowed = res.workflows.filter((t) =>
          canRunWorkflowType(role, t.workflow_type),
        )
        setTypes(allowed)
        if (defaultWorkflowType) {
          setWorkflowType(defaultWorkflowType)
        } else if (!workflowType && allowed[0]) {
          setWorkflowType(allowed[0].workflow_type)
        }
      })
      .catch(() => {
        if (!cancelled && defaultWorkflowType) {
          setWorkflowType(defaultWorkflowType)
        }
      })
    return () => {
      cancelled = true
    }
  }, [user?.role, defaultWorkflowType])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setResult(null)
    const trimmed = request.trim()
    if (!trimmed) {
      setError('Request text is required.')
      return
    }
    setLoading(true)
    try {
      const run = await workflowsApi.run({
        request: trimmed,
        workflow_type: workflowType || null,
      })
      setResult(run)
      if (
        run.approval_status === 'awaiting' ||
        run.status === 'awaiting_human_approval'
      ) {
        notify({
          tone: 'warning',
          title: 'Approval required',
          message: `Workflow ${run.workflow_id} is waiting for human approval.`,
        })
      } else if ((run.status || '').includes('reject')) {
        notify({
          tone: 'danger',
          title: 'Workflow rejected',
          message: run.decision?.outcome || run.status,
        })
      } else {
        notify({
          tone: 'success',
          title: 'Workflow completed',
          message: `${workflowTypeLabel(run.workflow_type)} · ${run.status}`,
        })
      }
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : 'Failed to run workflow.'
      setError(message)
      notify({ tone: 'danger', title: 'Workflow failed', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="stack-md">
      <div className="card">
        <div className="card-header">
          <div>
            <h2>{title}</h2>
            <p className="muted" style={{ marginTop: '0.25rem' }}>
              {description}
            </p>
          </div>
        </div>
        <form className="card-body form-grid" onSubmit={onSubmit}>
          <div className="form-row">
            <label htmlFor="workflow-type">Workflow</label>
            <select
              id="workflow-type"
              className="select"
              value={workflowType}
              disabled={lockedType || loading}
              onChange={(e) => setWorkflowType(e.target.value)}
            >
              {!lockedType ? <option value="">Auto-route from request</option> : null}
              {types.map((t) => (
                <option key={t.workflow_type} value={t.workflow_type}>
                  {t.name || workflowTypeLabel(t.workflow_type)}
                </option>
              ))}
              {lockedType &&
              workflowType &&
              !types.some((t) => t.workflow_type === workflowType) ? (
                <option value={workflowType}>
                  {workflowTypeLabel(workflowType)}
                </option>
              ) : null}
            </select>
            <span className="form-hint">
              Optional explicit type. Your identity comes from the signed-in session.
            </span>
          </div>
          <div className="form-row">
            <label htmlFor="workflow-request">Request</label>
            <textarea
              id="workflow-request"
              className="textarea"
              value={request}
              disabled={loading}
              placeholder={placeholder}
              onChange={(e) => setRequest(e.target.value)}
              required
            />
          </div>
          {error ? (
            <div className="badge badge-danger" role="alert">
              {error}
            </div>
          ) : null}
          <div className="split">
            <Button type="submit" variant="primary" disabled={loading}>
              {loading ? 'Running workflow…' : 'Run workflow'}
            </Button>
            {result ? (
              <Button
                type="button"
                onClick={() => navigate(`/workflows/${result.workflow_id}`)}
              >
                Open detail
              </Button>
            ) : null}
          </div>
        </form>
      </div>
      {loading ? (
        <div className="card card-body">
          <div className="spinner" aria-hidden />
          <p className="muted" style={{ textAlign: 'center' }}>
            Specialized agents are collaborating on this request…
          </p>
        </div>
      ) : null}
      {result ? <WorkflowResultBanner workflow={result} /> : null}
    </div>
  )
}
