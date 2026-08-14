import { BrandMark } from '../Brand'
import { useAuth } from '../../context/AuthContext'
import { roleLabel } from '../../utils/rbac'
import { Button } from '../ui/Primitives'

type Props = {
  pendingApprovals: number
  onToggleSidebar: () => void
}

export function Topbar({ pendingApprovals, onToggleSidebar }: Props) {
  const { user, logout } = useAuth()
  if (!user) return null

  const initials = user.username.slice(0, 2).toUpperCase()

  return (
    <header className="topbar">
      <div className="split">
        <button
          type="button"
          className="icon-btn"
          aria-label="Toggle navigation"
          onClick={onToggleSidebar}
        >
          ☰
        </button>
        <div className="brand">
          <BrandMark size={32} />
          <div className="brand-text">
            <div className="brand-name">WorkSphere AI</div>
            <div className="brand-org">{user.organization_id}</div>
          </div>
        </div>
      </div>

      <div className="topbar-actions">
        <div
          className="user-chip"
          title={pendingApprovals > 0 ? `${pendingApprovals} items need attention` : 'No alerts'}
        >
          <span
            className="notification-dot"
            aria-hidden={pendingApprovals === 0}
            data-active={pendingApprovals > 0}
          />
          <span className="muted" style={{ fontSize: '0.78rem' }}>
            {pendingApprovals > 0
              ? `${pendingApprovals} alert${pendingApprovals === 1 ? '' : 's'}`
              : 'No alerts'}
          </span>
        </div>
        <div className="user-chip">
          <div className="user-avatar" aria-hidden>
            {initials}
          </div>
          <div className="user-meta">
            <strong>{user.username}</strong>
            <span>{roleLabel(user.role)}</span>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={logout} aria-label="Log out">
          Log out
        </Button>
      </div>
    </header>
  )
}
