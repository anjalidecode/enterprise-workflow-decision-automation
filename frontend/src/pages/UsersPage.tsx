import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { usersApi } from '../api'
import { ApiClientError } from '../api/client'
import { Button, LoadingBlock, Modal, StatePanel, StatusBadge } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import type { ManagedUser, Role } from '../types/api'
import { formatDateTime } from '../utils/format'
import { roleLabel } from '../utils/rbac'

const PAGE_SIZE = 50
const ASSIGNABLE_ROLES: Exclude<Role, 'admin'>[] = ['employee', 'manager', 'hr']
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function displayName(user: ManagedUser): string {
  return user.full_name?.trim() || user.username
}

export function UsersPage() {
  const { user: currentUser } = useAuth()
  const { notify } = useToast()
  const [items, setItems] = useState<ManagedUser[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [offset, setOffset] = useState(0)

  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteName, setInviteName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<Exclude<Role, 'admin'>>('employee')
  const [inviteLoading, setInviteLoading] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteLink, setInviteLink] = useState<string | null>(null)

  const [detail, setDetail] = useState<ManagedUser | null>(null)
  const [pendingRole, setPendingRole] = useState<Role | ''>('')
  const [confirm, setConfirm] = useState<
    | { type: 'role'; user: ManagedUser; role: Role }
    | { type: 'deactivate'; user: ManagedUser }
    | null
  >(null)
  const [actionLoading, setActionLoading] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await usersApi.list({
        search: search.trim() || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
        limit: PAGE_SIZE,
        offset,
      })
      setItems(res.users)
      setTotal(res.total)
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to load users.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [roleFilter, statusFilter, offset])

  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function resetInvite() {
    setInviteName('')
    setInviteEmail('')
    setInviteRole('employee')
    setInviteError(null)
    setInviteLink(null)
    setInviteLoading(false)
  }

  async function onInvite(event: FormEvent) {
    event.preventDefault()
    setInviteError(null)
    if (!inviteName.trim() || !inviteEmail.trim()) {
      setInviteError('Full name and work email are required.')
      return
    }
    if (!EMAIL_RE.test(inviteEmail.trim())) {
      setInviteError('Enter a valid work email address.')
      return
    }
    setInviteLoading(true)
    try {
      const result = await usersApi.invite({
        full_name: inviteName.trim(),
        email: inviteEmail.trim(),
        role: inviteRole,
      })
      setInviteLink(result.invitation.activation_path)
      notify({
        tone: 'success',
        title: 'Invitation created',
        message: result.message,
      })
      await load()
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : 'Unable to send invitation.'
      setInviteError(message)
      notify({ tone: 'danger', title: 'Invitation failed', message })
    } finally {
      setInviteLoading(false)
    }
  }

  async function applyRole(target: ManagedUser, role: Role) {
    setActionLoading(true)
    try {
      const updated = await usersApi.updateRole(target.user_id, role)
      setDetail(updated)
      notify({
        tone: 'success',
        title: 'Role updated',
        message: `${displayName(updated)} is now ${roleLabel(updated.role)}.`,
      })
      await load()
    } catch (err) {
      const message = err instanceof ApiClientError ? err.message : 'Unable to change role.'
      notify({ tone: 'danger', title: 'Role change failed', message })
    } finally {
      setActionLoading(false)
      setConfirm(null)
    }
  }

  async function applyDeactivate(target: ManagedUser) {
    setActionLoading(true)
    try {
      const updated = await usersApi.deactivate(target.user_id)
      setDetail(updated)
      notify({
        tone: 'success',
        title: 'Account deactivated',
        message: `${displayName(updated)} can no longer sign in.`,
      })
      await load()
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : 'Unable to deactivate this account.'
      notify({ tone: 'danger', title: 'Deactivation failed', message })
    } finally {
      setActionLoading(false)
      setConfirm(null)
    }
  }

  async function applyActivate(target: ManagedUser) {
    setActionLoading(true)
    try {
      const updated = await usersApi.activate(target.user_id)
      setDetail(updated)
      notify({
        tone: 'success',
        title: 'Account activated',
        message: `${displayName(updated)} can sign in again.`,
      })
      await load()
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : 'Unable to activate this account.'
      notify({ tone: 'danger', title: 'Activation failed', message })
    } finally {
      setActionLoading(false)
    }
  }

  const empty = useMemo(() => !loading && !error && items.length === 0, [loading, error, items])

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="breadcrumbs">
            <Link to="/dashboard">Home</Link>
            <span>/</span>
            <Link to="/settings">Settings</Link>
            <span>/</span>
            <span>User Management</span>
          </div>
          <h1>User Management</h1>
          <p>
            Invite people to {currentUser?.organization_id} and assign operational roles.
            Privileged access is enforced by the server, not this page.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => {
            resetInvite()
            setInviteOpen(true)
          }}
        >
          Invite User
        </Button>
      </div>

      <div className="filters">
        <input
          className="input"
          placeholder="Search name or email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              setOffset(0)
              void load()
            }
          }}
          aria-label="Search users"
        />
        <select
          className="select"
          value={roleFilter}
          onChange={(e) => {
            setOffset(0)
            setRoleFilter(e.target.value)
          }}
          aria-label="Filter by role"
        >
          <option value="">All roles</option>
          <option value="employee">Employee</option>
          <option value="manager">Manager</option>
          <option value="hr">HR</option>
          <option value="admin">Admin</option>
        </select>
        <select
          className="select"
          value={statusFilter}
          onChange={(e) => {
            setOffset(0)
            setStatusFilter(e.target.value)
          }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="invited">Invited</option>
          <option value="inactive">Inactive</option>
        </select>
        <Button
          variant="secondary"
          onClick={() => {
            setOffset(0)
            void load()
          }}
          disabled={loading}
        >
          Search
        </Button>
      </div>

      {loading ? <LoadingBlock label="Loading users…" /> : null}
      {!loading && error ? (
        <StatePanel
          variant="error"
          title="Unable to load users"
          message={error}
          action={
            <Button variant="primary" onClick={() => void load()}>
              Retry
            </Button>
          }
        />
      ) : null}
      {empty ? (
        <StatePanel
          title="No users found"
          message="Invite a teammate to get started, or adjust your filters."
        />
      ) : null}
      {!loading && !error && items.length > 0 ? (
        <div className="card">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.user_id}>
                    <td>
                      <strong>{displayName(item)}</strong>
                    </td>
                    <td>{item.username}</td>
                    <td>{roleLabel(item.role)}</td>
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>
                      <div className="split" style={{ gap: '0.4rem' }}>
                        <Button size="sm" onClick={() => setDetail(item)}>
                          View
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pageCount > 1 ? (
            <div className="card-body split" style={{ justifyContent: 'space-between' }}>
              <span className="muted">
                Page {page} of {pageCount} · {total} users
              </span>
              <div className="split" style={{ gap: '0.5rem' }}>
                <Button
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      <Modal
        open={inviteOpen}
        title="Invite User"
        onClose={() => setInviteOpen(false)}
        actions={
          inviteLink ? (
            <Button variant="primary" onClick={() => setInviteOpen(false)}>
              Done
            </Button>
          ) : (
            <Button onClick={() => setInviteOpen(false)} disabled={inviteLoading}>
              Cancel
            </Button>
          )
        }
      >
        {inviteLink ? (
          <div className="stack-sm">
            <p>
              Invitation created. Email delivery is not enabled yet — share this activation
              link with the user.
            </p>
            <code className="invite-link">{inviteLink}</code>
          </div>
        ) : (
          <form id="invite-user-form" className="form-grid" onSubmit={onInvite} noValidate>
            <div className="form-row">
              <label htmlFor="invite-name">Full name</label>
              <input
                id="invite-name"
                className="input"
                value={inviteName}
                onChange={(e) => setInviteName(e.target.value)}
                disabled={inviteLoading}
                required
              />
            </div>
            <div className="form-row">
              <label htmlFor="invite-email">Work email</label>
              <input
                id="invite-email"
                className="input"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                disabled={inviteLoading}
                required
              />
            </div>
            <div className="form-row">
              <label htmlFor="invite-role">Role</label>
              <select
                id="invite-role"
                className="select"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as Exclude<Role, 'admin'>)}
                disabled={inviteLoading}
              >
                {ASSIGNABLE_ROLES.map((role) => (
                  <option key={role} value={role}>
                    {roleLabel(role)}
                  </option>
                ))}
              </select>
            </div>
            {inviteError ? (
              <div className="badge badge-danger" role="alert">
                {inviteError}
              </div>
            ) : null}
            <Button type="submit" variant="primary" disabled={inviteLoading}>
              {inviteLoading ? 'Sending…' : 'Send Invitation'}
            </Button>
          </form>
        )}
      </Modal>

      <Modal
        open={Boolean(detail)}
        title={detail ? displayName(detail) : 'User'}
        onClose={() => setDetail(null)}
        actions={<Button onClick={() => setDetail(null)}>Close</Button>}
      >
        {detail ? (
          <div className="stack-sm">
            <div className="metric-row">
              <span className="muted">Email</span>
              <strong>{detail.username}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Role</span>
              <strong>{roleLabel(detail.role)}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Organization</span>
              <strong>{detail.organization_id}</strong>
            </div>
            <div className="metric-row">
              <span className="muted">Status</span>
              <StatusBadge status={detail.status} />
            </div>
            <div className="metric-row">
              <span className="muted">Created</span>
              <strong>{formatDateTime(detail.created_at)}</strong>
            </div>
            {detail.role !== 'admin' ? (
              <div className="form-row">
                <label htmlFor="change-role">Change role</label>
                <div className="split" style={{ gap: '0.5rem' }}>
                  <select
                    id="change-role"
                    className="select"
                    value={pendingRole || detail.role}
                    onChange={(e) => setPendingRole(e.target.value as Role)}
                  >
                    {ASSIGNABLE_ROLES.map((role) => (
                      <option key={role} value={role}>
                        {roleLabel(role)}
                      </option>
                    ))}
                  </select>
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={actionLoading || (pendingRole || detail.role) === detail.role}
                    onClick={() => {
                      const next = (pendingRole || detail.role) as Role
                      setConfirm({ type: 'role', user: detail, role: next })
                    }}
                  >
                    Update
                  </Button>
                </div>
              </div>
            ) : (
              <p className="muted">Administrator role changes are protected by the server.</p>
            )}
            {detail.status === 'inactive' ? (
              <Button
                variant="primary"
                disabled={actionLoading || detail.user_id === currentUser?.user_id}
                onClick={() => void applyActivate(detail)}
              >
                Activate user
              </Button>
            ) : detail.status === 'active' ? (
              <Button
                variant="danger"
                disabled={actionLoading || detail.user_id === currentUser?.user_id}
                onClick={() => setConfirm({ type: 'deactivate', user: detail })}
              >
                Deactivate user
              </Button>
            ) : (
              <p className="muted">
                This invited user must set a password with the activation link before they
                can sign in.
              </p>
            )}
          </div>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(confirm)}
        title={confirm?.type === 'deactivate' ? 'Deactivate this account?' : 'Confirm role change'}
        onClose={() => setConfirm(null)}
        actions={
          <>
            <Button onClick={() => setConfirm(null)} disabled={actionLoading}>
              Cancel
            </Button>
            <Button
              variant={confirm?.type === 'deactivate' ? 'danger' : 'primary'}
              disabled={actionLoading}
              onClick={() => {
                if (!confirm) return
                if (confirm.type === 'deactivate') void applyDeactivate(confirm.user)
                else void applyRole(confirm.user, confirm.role)
              }}
            >
              Confirm
            </Button>
          </>
        }
      >
        {confirm?.type === 'deactivate' ? (
          <p>The user will no longer be able to sign in.</p>
        ) : confirm?.type === 'role' ? (
          <p>
            Change {displayName(confirm.user)}&apos;s role from {roleLabel(confirm.user.role)} to{' '}
            {roleLabel(confirm.role)}?
          </p>
        ) : null}
      </Modal>
    </div>
  )
}
