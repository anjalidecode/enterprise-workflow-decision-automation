import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import { AuthShell } from '../components/layout/AuthShell'
import { Button } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

export function LoginPage() {
  const { login } = useAuth()
  const { notify } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const from =
    (location.state as { from?: string } | null)?.from &&
    (location.state as { from?: string }).from !== '/login'
      ? (location.state as { from: string }).from
      : '/dashboard'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!username.trim() || !password) {
      setError('Work email and password are required.')
      return
    }
    setLoading(true)
    try {
      await login(username.trim(), password, remember)
      notify({ tone: 'success', title: 'Signed in', message: 'Welcome to WorkSphere AI.' })
      navigate(from, { replace: true })
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.message
          : 'Unable to sign in. Check your credentials.'
      setError(message)
      notify({ tone: 'danger', title: 'Login failed', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      <div className="login-card">
        <h2>Sign in</h2>
        <p className="muted" style={{ marginBottom: '1.25rem' }}>
          Access your organization’s HR workflow workspace.
        </p>
        <form className="form-grid" onSubmit={onSubmit} noValidate>
          <div className="form-row">
            <label htmlFor="username">Work email or username</label>
            <input
              id="username"
              className="input"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                className="input"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>
          <label className="check-row">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            Remember me
          </label>
          {error ? (
            <div className="badge badge-danger" role="alert">
              {error}
            </div>
          ) : null}
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
        <p className="auth-switch">
          New to WorkSphere AI? <Link to="/register">Create an account</Link>
        </p>
        <p className="auth-switch">
          Have an invitation? <Link to="/activate">Activate your account</Link>
        </p>
        <details className="dev-access">
          <summary>Development access</summary>
          <p>
            Local demo accounts remain available for evaluation. Ask your administrator
            for workspace credentials in production.
          </p>
        </details>
      </div>
    </AuthShell>
  )
}
