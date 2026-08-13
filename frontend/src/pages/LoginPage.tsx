import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import { Button } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { ToastViewport } from '../components/ui/Primitives'

export function LoginPage() {
  const { login } = useAuth()
  const { notify, toasts, dismiss } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const from =
    (location.state as { from?: string } | null)?.from &&
    (location.state as { from?: string }).from !== '/login'
      ? (location.state as { from: string }).from
      : '/dashboard'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!username.trim() || !password) {
      setError('Username and password are required.')
      return
    }
    setLoading(true)
    try {
      await login(username.trim(), password)
      notify({ tone: 'success', title: 'Signed in', message: 'Welcome back.' })
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
    <div className="login-page">
      <section className="login-hero" aria-label="Product introduction">
        <div>
          <div className="brand-mark" style={{ width: 48, height: 48, fontSize: '1rem' }}>
            EW
          </div>
          <h1>Enterprise Workflow Decision Automation</h1>
          <p>
            AI-powered HR operations with specialized agents, policy-aware decisions,
            human approval, and full auditability — not a chatbot.
          </p>
        </div>
        <p style={{ opacity: 0.75, fontSize: '0.9rem' }}>
          Group 1 · Modules 1–5D · FastAPI + JWT + PostgreSQL + React
        </p>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <h2>Sign in</h2>
          <p className="muted" style={{ marginBottom: '1.25rem' }}>
            Use your organization credentials to access the HR workflow platform.
          </p>
          <form className="form-grid" onSubmit={onSubmit} noValidate>
            <div className="form-row">
              <label htmlFor="username">Username</label>
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
              <input
                id="password"
                type="password"
                className="input"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div className="demo-creds">
            <strong style={{ color: 'var(--text)' }}>Development demo accounts</strong>
            <p style={{ marginTop: '0.35rem' }}>
              Password for all: <code>dev-password-123</code>
            </p>
            <p style={{ marginTop: '0.35rem' }}>
              <code>employee001</code> · <code>manager001</code> · <code>hr001</code> ·{' '}
              <code>admin001</code>
            </p>
          </div>
        </div>
      </section>
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </div>
  )
}
