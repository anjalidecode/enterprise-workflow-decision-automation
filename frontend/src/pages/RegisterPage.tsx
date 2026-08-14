import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../api'
import { ApiClientError } from '../api/client'
import { AuthShell } from '../components/layout/AuthShell'
import { Button } from '../components/ui/Primitives'
import { useToast } from '../context/ToastContext'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function RegisterPage() {
  const { notify } = useToast()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [organization, setOrganization] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!fullName.trim() || !email.trim() || !organization.trim() || !password || !confirm) {
      setError('All fields are required.')
      return
    }
    if (!EMAIL_RE.test(email.trim())) {
      setError('Enter a valid work email address.')
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
      const result = await authApi.register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        confirm_password: confirm,
        organization_name: organization.trim(),
      })
      notify({
        tone: 'success',
        title: 'Account created successfully.',
        message: result.message || 'You can now sign in.',
      })
      navigate('/login', { replace: true })
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : 'Unable to create your account.'
      setError(message)
      notify({ tone: 'danger', title: 'Registration failed', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      <div className="login-card">
        <h2>Create an account</h2>
        <p className="muted" style={{ marginBottom: '1.25rem' }}>
          Set up your organization workspace. Privileged roles are assigned by the
          platform — not selected here.
        </p>
        <form className="form-grid" onSubmit={onSubmit} noValidate>
          <div className="form-row">
            <label htmlFor="full-name">Full name</label>
            <input
              id="full-name"
              className="input"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="email">Work email</label>
            <input
              id="email"
              type="email"
              className="input"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="organization">Organization / company name</label>
            <input
              id="organization"
              className="input"
              autoComplete="organization"
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
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
                autoComplete="new-password"
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
            <span className="form-hint">At least 10 characters, with a letter and a number.</span>
          </div>
          <div className="form-row">
            <label htmlFor="confirm-password">Confirm password</label>
            <input
              id="confirm-password"
              type={showPassword ? 'text' : 'password'}
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
            {loading ? 'Creating account…' : 'Create account'}
          </Button>
        </form>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </AuthShell>
  )
}
