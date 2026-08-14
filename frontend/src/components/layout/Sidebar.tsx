import { NavLink } from 'react-router-dom'
import { BrandMark } from '../Brand'
import { useAuth } from '../../context/AuthContext'
import { navForRole, navLabel } from '../../utils/rbac'

const ICONS: Record<string, string> = {
  dashboard: '▣',
  workflows: '⇄',
  requests: '✎',
  approvals: '✓',
  employees: '👤',
  leave: '◷',
  attendance: '◷',
  recruitment: '⊕',
  onboarding: '↗',
  performance: '★',
  training: '▤',
  offboarding: '↘',
  services: '☰',
  audit: '◉',
  analytics: '▦',
  settings: '⚙',
}

export function Sidebar({ open }: { open: boolean }) {
  const { user } = useAuth()
  if (!user) return null
  const items = navForRole(user.role)

  return (
    <aside className="sidebar" aria-label="Primary" data-open={open}>
      <div className="sidebar-brand">
        <BrandMark size={28} />
        <div>
          <div className="sidebar-product">WorkSphere AI</div>
          <div className="sidebar-org">{user.organization_id}</div>
        </div>
      </div>
      <div className="nav-section-label">Workspace</div>
      <nav>
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <span aria-hidden>{ICONS[item.icon] || '•'}</span>
            <span>{navLabel(item, user.role)}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
