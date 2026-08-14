import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { roleLabel } from '../utils/rbac'

export function SettingsPage() {
  const { user, logout } = useAuth()

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <span>Settings</span>
          </div>
          <h1>Settings</h1>
          <p>Profile and session for your WorkSphere AI workspace.</p>
        </div>
      </div>

      <div className="panel-grid">
        <div className="card">
          <div className="card-header">
            <h2>Profile</h2>
          </div>
          <div className="card-body stack-sm">
            <div className="metric-row">
              <span className="muted">Username</span>
              <strong>{user?.username}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Role</span>
              <strong>{roleLabel(user?.role || 'employee')}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Organization</span>
              <strong>{user?.organization_id}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Employee ID</span>
              <strong>{user?.employee_id || '—'}</strong>
            </div>
            <button type="button" className="btn btn-secondary" onClick={logout}>
              Log out
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Workspace</h2>
          </div>
          <div className="card-body stack-sm">
            <p className="muted">
              Role changes and organization administration are controlled by authorized
              administrators. This application never stores secrets in the browser beyond
              your session token.
            </p>
            {user?.role === 'admin' ? (
              <Link className="btn btn-primary" to="/users">
                User Management
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
