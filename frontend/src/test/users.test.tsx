import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import App from '../App'
import { setStoredToken } from '../api/client'
import type { ManagedUser } from '../types/api'
import { demoUsers, jsonResponse, renderWithProviders } from './testUtils'

const users: ManagedUser[] = [
  {
    user_id: 'u-admin',
    username: 'admin001',
    full_name: 'Demo Admin',
    organization_id: 'demo-org',
    role: 'admin',
    employee_id: null,
    status: 'active',
    is_active: true,
    created_at: '2026-08-01T10:00:00Z',
  },
  {
    user_id: 'u-rahul',
    username: 'rahul@worksphere.test',
    full_name: 'Rahul',
    organization_id: 'demo-org',
    role: 'employee',
    employee_id: null,
    status: 'active',
    is_active: true,
    created_at: '2026-08-02T10:00:00Z',
  },
]

function usersFetch(options?: {
  list?: ManagedUser[]
  inviteError?: { status: number; code: string; message: string }
  patchError?: { status: number; code: string; message: string }
}) {
  const list = options?.list ?? users
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = (init?.method || 'GET').toUpperCase()
    if (url.includes('/auth/me')) return jsonResponse(demoUsers.admin)
    if (url.includes('/users/invite') && method === 'POST') {
      if (options?.inviteError) {
        return jsonResponse(
          { error: { code: options.inviteError.code, message: options.inviteError.message } },
          options.inviteError.status,
        )
      }
      const body = JSON.parse(String(init?.body || '{}')) as {
        full_name: string
        email: string
        role: string
      }
      return jsonResponse({
        message: 'Invitation created successfully. Invitation notification generated.',
        user: {
          user_id: 'u-new',
          username: body.email,
          full_name: body.full_name,
          organization_id: 'demo-org',
          role: body.role,
          employee_id: null,
          status: 'invited',
          is_active: false,
          created_at: '2026-08-15T10:00:00Z',
        },
        invitation: {
          expires_at: '2026-08-22T10:00:00Z',
          activation_path: '/activate?token=abc',
          activation_token: 'abc',
        },
        notification: {
          event_type: 'USER_INVITED',
          status: 'generated',
          message: 'Invitation notification generated.',
          provider: 'console',
        },
      })
    }
    if (url.includes('/users/u-rahul/deactivate') && method === 'POST') {
      return jsonResponse({ ...users[1], status: 'inactive', is_active: false })
    }
    if (url.includes('/users/u-rahul') && method === 'PATCH') {
      if (options?.patchError) {
        return jsonResponse(
          { error: { code: options.patchError.code, message: options.patchError.message } },
          options.patchError.status,
        )
      }
      const body = JSON.parse(String(init?.body || '{}')) as { role: string }
      return jsonResponse({ ...users[1], role: body.role })
    }
    if (url.includes('/employees')) {
      return jsonResponse({
        employees: [
          {
            employee_id: 'E002',
            name: 'Jordan Chen',
            department: 'Finance',
            job_role: 'Financial Analyst',
            employment_status: 'active',
            bound_user_id: null,
            bound_username: null,
            available: true,
          },
        ],
      })
    }
    if (url.includes('/users')) {
      return jsonResponse({ users: list, total: list.length, limit: 50, offset: 0 })
    }
    return jsonResponse({ workflows: [], total: 0, limit: 50, offset: 0 })
  })
}

describe('user management', () => {
  beforeEach(() => {
    setStoredToken('token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setStoredToken(null)
  })

  it('shows the admin user management page and list', async () => {
    vi.stubGlobal('fetch', usersFetch())
    renderWithProviders(<App />, { route: '/users', token: 'token' })
    expect(await screen.findByRole('heading', { name: /user management/i })).toBeInTheDocument()
    expect(await screen.findByText('Rahul')).toBeInTheDocument()
    expect(screen.getByText('rahul@worksphere.test')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /invite user/i })).toBeInTheDocument()
  }, 15000)

  it('redirects non-admin users away from user management', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/auth/me')) return jsonResponse(demoUsers.employee)
        if (url.includes('/users')) {
          return jsonResponse(
            { error: { code: 'FORBIDDEN', message: 'You do not have permission to perform this action.' } },
            403,
          )
        }
        return jsonResponse({ workflows: [], total: 0, limit: 200, offset: 0 })
      }),
    )
    renderWithProviders(<App />, { route: '/users', token: 'token' })
    expect(await screen.findByRole('heading', { name: /worksphere ai/i })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /user management/i })).not.toBeInTheDocument()
  }, 15000)

  it('validates the invite form', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', usersFetch())
    renderWithProviders(<App />, { route: '/users', token: 'token' })
    await screen.findByRole('heading', { name: /user management/i })
    await user.click(screen.getByRole('button', { name: /invite user/i }))
    expect(await screen.findByRole('heading', { name: /invite user/i })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /send invitation/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/full name and work email/i)
  }, 15000)

  it('sends an invitation', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', usersFetch())
    renderWithProviders(<App />, { route: '/users', token: 'token' })
    await screen.findByRole('heading', { name: /user management/i })
    await user.click(screen.getByRole('button', { name: /invite user/i }))
    await user.type(screen.getByLabelText(/full name/i), 'Amit')
    await user.type(screen.getByLabelText(/work email/i), 'amit@worksphere.test')
    await user.selectOptions(screen.getByLabelText(/^role$/i), 'hr')
    await user.click(screen.getByRole('button', { name: /send invitation/i }))
    expect(
      await screen.findByText('/activate?token=abc'),
    ).toBeInTheDocument()
    expect(
      screen.getAllByText(/Invitation created successfully\. Invitation notification generated\./i)
        .length,
    ).toBeGreaterThan(0)
  }, 15000)

  it('shows invite permission errors', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      usersFetch({
        inviteError: { status: 403, code: 'FORBIDDEN', message: 'You do not have permission to perform this action.' },
      }),
    )
    renderWithProviders(<App />, { route: '/users', token: 'token' })
    await screen.findByRole('heading', { name: /user management/i })
    await user.click(screen.getByRole('button', { name: /invite user/i }))
    await user.type(screen.getByLabelText(/full name/i), 'Amit')
    await user.type(screen.getByLabelText(/work email/i), 'amit@worksphere.test')
    await user.selectOptions(screen.getByLabelText(/^role$/i), 'hr')
    await user.click(screen.getByRole('button', { name: /send invitation/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/do not have permission/i)
  }, 15000)

  it('confirms a role change', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', usersFetch())
    renderWithProviders(<App />, { route: '/users', token: 'token' })
    await screen.findByText('Rahul')
    const row = screen.getByText('Rahul').closest('tr')
    expect(row).toBeTruthy()
    await user.click(within(row as HTMLElement).getByRole('button', { name: /view/i }))
    const dialog = await screen.findByRole('dialog', { name: /rahul/i })
    await user.selectOptions(within(dialog).getByLabelText(/change role/i), 'manager')
    await user.click(within(dialog).getByRole('button', { name: /update/i }))
    expect(await screen.findByText(/change rahul's role from employee to manager/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => {
      expect(screen.getByText(/rahul is now manager/i)).toBeInTheDocument()
    })
  }, 15000)

  it('confirms deactivation', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', usersFetch())
    renderWithProviders(<App />, { route: '/users', token: 'token' })
    await screen.findByText('Rahul')
    const row = screen.getByText('Rahul').closest('tr')
    await user.click(within(row as HTMLElement).getByRole('button', { name: /view/i }))
    const dialog = await screen.findByRole('dialog', { name: /rahul/i })
    await user.click(within(dialog).getByRole('button', { name: /deactivate user/i }))
    expect(await screen.findByText(/the user will no longer be able to sign in/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => {
      expect(screen.getByText(/can no longer sign in/i)).toBeInTheDocument()
    })
  }, 15000)
})
