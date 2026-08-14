export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  const minutes = Math.floor(seconds / 60)
  const rem = Math.round(seconds % 60)
  return `${minutes}m ${rem}s`
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${Math.round(value * 100)}%`
}

export function formatConfidence(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  const normalized = value > 1 ? value / 100 : value
  return `${Math.round(normalized * 100)}%`
}

export function shortId(id: string, size = 8): string {
  if (!id) return '—'
  return id.length <= size ? id : `${id.slice(0, size)}…`
}

export function titleCaseStatus(status: string): string {
  if (!status) return 'Unknown'
  return status
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function workflowTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    leave_attendance: 'Leave & Attendance',
    recruitment: 'Recruitment',
    onboarding: 'Onboarding',
    attendance: 'Attendance',
    performance: 'Performance',
    training: 'Training',
    offboarding: 'Offboarding',
    hr_services: 'HR Services',
  }
  return labels[type] || titleCaseStatus(type)
}

export function statusTone(
  status: string,
): 'neutral' | 'info' | 'success' | 'warning' | 'danger' {
  const s = (status || '').toLowerCase()
  if (s.includes('complet') || s === 'approved' || s === 'success') return 'success'
  if (s.includes('await') || s.includes('pending') || s.includes('paused')) return 'warning'
  if (s.includes('reject') || s.includes('fail') || s.includes('error')) return 'danger'
  if (s.includes('run') || s.includes('progress') || s.includes('active')) return 'info'
  return 'neutral'
}

/** Canonical agentic pipeline stages for visualization. */
export const PIPELINE_STAGES = [
  { key: 'request', label: 'Request' },
  { key: 'planner', label: 'Planner' },
  { key: 'research', label: 'Research' },
  { key: 'policy', label: 'Policy' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'decision', label: 'Decision' },
  { key: 'validation', label: 'Validation' },
  { key: 'action', label: 'Action / Approval' },
  { key: 'response', label: 'Response' },
] as const

export function inferStageStatus(
  stageKey: string,
  currentStage: string,
  workflowStatus: string,
  agents: Record<string, unknown>[],
): 'pending' | 'active' | 'done' | 'blocked' {
  const status = (workflowStatus || '').toLowerCase()
  const current = (currentStage || '').toLowerCase()
  const agentNames = agents
    .map((a) => String(a.name || a.agent || a.agent_name || '').toLowerCase())
    .filter(Boolean)

  const stageIndex = PIPELINE_STAGES.findIndex((s) => s.key === stageKey)
  let currentIndex = PIPELINE_STAGES.findIndex(
    (s) => current.includes(s.key) || s.key.includes(current),
  )

  if (currentIndex < 0) {
    if (status.includes('await')) currentIndex = PIPELINE_STAGES.findIndex((s) => s.key === 'action')
    else if (status.includes('complet')) currentIndex = PIPELINE_STAGES.length
    else if (status.includes('reject') || status.includes('fail')) {
      currentIndex = Math.max(
        PIPELINE_STAGES.findIndex((s) => s.key === 'decision'),
        0,
      )
    }
  }

  const matchedAgent = agentNames.some(
    (name) => name.includes(stageKey) || stageKey.includes(name.split('_').pop() || ''),
  )

  if (status.includes('fail') || status.includes('error') || status.includes('reject')) {
    if (stageIndex === currentIndex) return 'blocked'
  }

  if (stageIndex < currentIndex || (status.includes('complet') && stageIndex < PIPELINE_STAGES.length)) {
    return 'done'
  }
  if (stageIndex === currentIndex || (matchedAgent && stageIndex <= currentIndex + 1)) {
    if (stageIndex === currentIndex) return 'active'
    return matchedAgent ? 'done' : 'pending'
  }
  if (matchedAgent) return 'done'
  return 'pending'
}

export function describeRecord(item: Record<string, unknown>): string {
  const title = String(
    item.name ||
      item.tool ||
      item.tool_name ||
      item.agent ||
      item.agent_name ||
      item.type ||
      item.action ||
      item.store ||
      item.memory_type ||
      '',
  )
  const status = item.status ? String(item.status) : ''
  const extra = String(item.summary || item.message || item.operation || item.key || '')
  return [title, status, extra].filter(Boolean).join(' · ') || 'Recorded step'
}
