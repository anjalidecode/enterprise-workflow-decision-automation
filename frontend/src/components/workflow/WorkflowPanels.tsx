import { Link } from 'react-router-dom'
import type { Workflow, WorkflowAudit, WorkflowMetrics } from '../../types/api'
import {
  PIPELINE_STAGES,
  formatConfidence,
  formatDurationMs,
  formatPercent,
  inferStageStatus,
  titleCaseStatus,
  workflowTypeLabel,
} from '../../utils/format'
import { StatusBadge } from '../ui/Primitives'

function agentLabel(agent: Record<string, unknown>): string {
  return String(agent.name || agent.agent || agent.agent_name || agent.stage || 'Agent')
}

function agentDetail(agent: Record<string, unknown>): string {
  const status = agent.status ? `Status: ${String(agent.status)}` : ''
  const order =
    agent.order != null || agent.sequence != null
      ? `Order: ${String(agent.order ?? agent.sequence)}`
      : ''
  return [status, order].filter(Boolean).join(' · ') || 'Executed as part of the agentic pipeline'
}

export function WorkflowTimeline({
  workflow,
  audit,
}: {
  workflow: Workflow
  audit: WorkflowAudit | null
}) {
  const agents = audit?.agents || workflow.audit?.agents || []

  return (
    <div className="timeline" aria-label="Workflow execution timeline">
      {PIPELINE_STAGES.map((stage) => {
        const status = inferStageStatus(
          stage.key,
          workflow.current_stage,
          workflow.status,
          agents,
        )
        const related = agents.find((a) => {
          const name = agentLabel(a).toLowerCase()
          return name.includes(stage.key) || stage.key.includes(name.split(/[\s_]/).pop() || '')
        })
        return (
          <div key={stage.key} className={`timeline-step ${status}`}>
            <div className="timeline-dot" aria-hidden>
              {status === 'done' ? '✓' : status === 'blocked' ? '!' : stage.label.charAt(0)}
            </div>
            <div className="timeline-body">
              <h4>
                {stage.label}{' '}
                <StatusBadge status={status === 'done' ? 'completed' : status} />
              </h4>
              <p>
                {related
                  ? `${agentLabel(related)} — ${agentDetail(related)}`
                  : status === 'active'
                    ? 'Currently executing this stage.'
                    : status === 'done'
                      ? 'Stage completed.'
                      : 'Awaiting upstream stages.'}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function DecisionPanel({ workflow }: { workflow: Workflow }) {
  const decision = workflow.decision
  if (!decision) {
    return (
      <div className="card">
        <div className="card-header">
          <h3>Decision</h3>
        </div>
        <div className="card-body muted">No decision recorded yet for this run.</div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3>Decision</h3>
        <StatusBadge status={decision.outcome || 'pending'} />
      </div>
      <div className="card-body stack-sm">
        <div className="split">
          <span className="muted">Confidence</span>
          <strong>{formatConfidence(decision.confidence)}</strong>
        </div>
        <div>
          <div className="muted" style={{ marginBottom: '0.25rem' }}>
            Rationale
          </div>
          <p>{decision.rationale || '—'}</p>
        </div>
        {decision.evidence.length > 0 ? (
          <div>
            <div className="muted" style={{ marginBottom: '0.25rem' }}>
              Evidence
            </div>
            <ul>
              {decision.evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {decision.blockers.length > 0 ? (
          <div>
            <div className="muted" style={{ marginBottom: '0.25rem' }}>
              Blockers
            </div>
            <ul>
              {decision.blockers.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {decision.warnings.length > 0 ? (
          <div>
            <div className="muted" style={{ marginBottom: '0.25rem' }}>
              Warnings
            </div>
            <ul>
              {decision.warnings.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <div className="split">
          {decision.requires_human_approval ? (
            <span className="badge badge-warning">Human approval required</span>
          ) : null}
          {decision.executable ? (
            <span className="badge badge-success">Executable</span>
          ) : (
            <span className="badge">Not executable</span>
          )}
        </div>
      </div>
    </div>
  )
}

export function MetricsPanel({ metrics }: { metrics: WorkflowMetrics | null }) {
  if (!metrics) {
    return (
      <div className="card">
        <div className="card-header">
          <h3>Metrics</h3>
        </div>
        <div className="card-body muted">Metrics unavailable for this workflow.</div>
      </div>
    )
  }

  const rows: [string, string][] = [
    ['Duration', formatDurationMs(metrics.duration_ms)],
    ['Agents', String(metrics.agent_count)],
    ['Tools', String(metrics.tool_count)],
    ['Tool success', formatPercent(metrics.tool_success_rate)],
    ['Actions', String(metrics.action_count)],
    ['Action success', formatPercent(metrics.action_success_rate)],
    ['Retries', String(metrics.retry_count)],
    ['Validation failed', metrics.validation_failed ? 'Yes' : 'No'],
    ['Approval required', metrics.human_approval_required ? 'Yes' : 'No'],
    ['Escalated', metrics.escalated ? 'Yes' : 'No'],
    ['Decision confidence', formatConfidence(metrics.decision_confidence)],
    ['Success', metrics.success ? 'Yes' : 'No'],
  ]

  return (
    <div className="card">
      <div className="card-header">
        <h3>Run metrics</h3>
        <StatusBadge status={metrics.status || 'unknown'} />
      </div>
      <div className="card-body">
        {rows.map(([label, value]) => (
          <div className="metric-row" key={label}>
            <span className="muted">{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

export function AuditSummary({ audit }: { audit: WorkflowAudit | null }) {
  if (!audit) {
    return (
      <div className="card">
        <div className="card-header">
          <h3>Audit</h3>
        </div>
        <div className="card-body muted">Audit snapshot unavailable.</div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3>Audit snapshot</h3>
        <StatusBadge status={audit.status || 'unknown'} />
      </div>
      <div className="card-body stack-sm">
        <div className="split">
          <span className="muted">Type</span>
          <span>{workflowTypeLabel(audit.workflow_type)}</span>
        </div>
        <div className="split">
          <span className="muted">Outcome</span>
          <span>{titleCaseStatus(audit.final_outcome || '—')}</span>
        </div>
        <div className="split">
          <span className="muted">Agents</span>
          <span>{audit.agents.length}</span>
        </div>
        <div className="split">
          <span className="muted">Tools</span>
          <span>{audit.tool_executions.length}</span>
        </div>
        <div className="split">
          <span className="muted">Memory accesses</span>
          <span>{audit.memory_accesses.length}</span>
        </div>
        <div className="split">
          <span className="muted">Actions</span>
          <span>{audit.actions.length}</span>
        </div>
        <div className="split">
          <span className="muted">Pending actions</span>
          <span>{audit.pending_actions.length}</span>
        </div>
        {audit.errors.length > 0 ? (
          <div>
            <div className="muted">Errors</div>
            <ul>
              {audit.errors.map((err) => (
                <li key={err}>{err}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function WorkflowResultBanner({ workflow }: { workflow: Workflow }) {
  return (
    <div className="card">
      <div className="card-body stack-sm">
        <div className="split" style={{ justifyContent: 'space-between' }}>
          <div>
            <div className="muted">Workflow</div>
            <Link to={`/workflows/${workflow.workflow_id}`} className="mono">
              {workflow.workflow_id}
            </Link>
          </div>
          <StatusBadge status={workflow.status} />
        </div>
        <div>
          <div className="muted">Final response</div>
          <p>{workflow.response || 'No final response yet.'}</p>
        </div>
        {workflow.decision ? (
          <div className="split">
            <StatusBadge status={workflow.decision.outcome || 'decision'} />
            <span className="muted">
              Confidence {formatConfidence(workflow.decision.confidence)}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}
