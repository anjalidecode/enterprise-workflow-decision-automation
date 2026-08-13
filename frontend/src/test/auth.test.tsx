import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import App from '../App'
import { setStoredToken } from '../api/client'
import { demoUsers, jsonResponse, renderWithProviders } from './testUtils'

describe('login and auth', () => {
  beforeEach(() => {
    setStoredToken(null)
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setStoredToken(null)
  })

  it('renders login form', async () => {
    renderWithProviders(<App />, { route: '/login' })
    expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByText(/development demo accounts/i)).toBeInTheDocument()
  })

  it('shows login failure', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          { error: { code: 'AUTHENTICATION_REQUIRED', message: 'Invalid credentials' } },
          401,
        ),
      ),
    )

    renderWithProviders(<App />, { route: '/login' })
    await user.type(screen.getByLabelText(/username/i), 'bad')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid credentials/i)
  })

  it('logs in successfully and reaches dashboard', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/auth/login')) {
          return jsonResponse({
            access_token: 'token-abc',
            token_type: 'bearer',
            expires_in: 3600,
            user: demoUsers.hr,
          })
        }
        if (url.includes('/auth/me')) return jsonResponse(demoUsers.hr)
        if (url.includes('/workflows?') || url.endsWith('/workflows')) {
          return jsonResponse({
            workflows: [],
            total: 0,
            limit: 200,
            offset: 0,
          })
        }
        if (url.includes('/workflows') && url.includes('awaiting')) {
          return jsonResponse({ workflows: [], total: 0, limit: 50, offset: 0 })
        }
        return jsonResponse({ workflows: [], total: 0, limit: 50, offset: 0 })
      }),
    )

    renderWithProviders(<App />, { route: '/login' })
    await user.type(screen.getByLabelText(/username/i), 'hr001')
    await user.type(screen.getByLabelText(/password/i), 'dev-password-123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /hr dashboard/i })).toBeInTheDocument()
    })
  })

  it('protects routes when unauthenticated', async () => {
    renderWithProviders(<App />, { route: '/dashboard' })
    expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })
})
