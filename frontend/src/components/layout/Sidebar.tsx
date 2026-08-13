import { NavLink } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { navForRole } from '../../utils/rbac'

const ICONS: Record<string, string> = {
  dashboard: '▣',
  workflows: '⇄',
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
  settings: '⚙',
}

export function Sidebar({ open }: { open: boolean }) {
  const { user } = useAuth()
  if (!user) return null
  const items = navForRole(user.role)

  return (
    <aside className="sidebar" aria-label="Primary" data-open={open}>
      <div className="nav-section-label">Operations</div>
      <nav>
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <span aria-hidden>{ICONS[item.icon] || '•'}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
