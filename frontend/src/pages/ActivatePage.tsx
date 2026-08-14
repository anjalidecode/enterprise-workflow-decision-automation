import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api'
import { ApiClientError } from '../api/client'
import { AuthShell } from '../components/layout/AuthShell'
import { Button } from '../components/ui/Primitives'
import { useToast } from '../context/ToastContext'

export function ActivatePage() {
  const { notify } = useToast()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const tokenFromQuery = params.get('token') || ''
  const [token, setToken] = useState(tokenFromQuery)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!token.trim() || !password || !confirm) {
      setError('Invitation token and password are required.')
      return
    }
    if (password !== confirm) {
      setError('Password and confirmation do not match.')
      return
    }
    if (password.length < 10 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setError('Password must be at least 10 characters and include a letter and a number.')
      return
    }
    setLoading(true)
    try {
      const result = await authApi.activate({
        token: token.trim(),
        password,
        confirm_password: confirm,
      })
      notify({
        tone: 'success',
        title: 'Account activated',
        message: result.message,
      })
      navigate('/login', { replace: true })
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : 'Unable to activate this account.'
      setError(message)
      notify({ tone: 'danger', title: 'Activation failed', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      <div className="login-card">
        <h2>Activate your account</h2>
        <p className="muted" style={{ marginBottom: '1.25rem' }}>
          Set a password to join your organization workspace. Your role is assigned by an
          administrator.
        </p>
        <form className="form-grid" onSubmit={onSubmit} noValidate>
          {!tokenFromQuery ? (
            <div className="form-row">
              <label htmlFor="invite-token">Invitation token</label>
              <input
                id="invite-token"
                className="input"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                disabled={loading}
                required
              />
            </div>
          ) : (
            <input type="hidden" value={token} readOnly />
          )}
          <div className="form-row">
            <label htmlFor="activate-password">Password</label>
            <input
              id="activate-password"
              type="password"
              className="input"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="activate-confirm">Confirm password</label>
            <input
              id="activate-confirm"
              type="password"
              className="input"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          {error ? (
            <div className="badge badge-danger" role="alert">
              {error}
            </div>
          ) : null}
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? 'Activating…' : 'Activate account'}
          </Button>
        </form>
        <p className="auth-switch">
          Already activated? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </AuthShell>
  )
}
