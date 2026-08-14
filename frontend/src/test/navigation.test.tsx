import { screen } from '@testing-library/react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import App from '../App'
import { setStoredToken } from '../api/client'
import { demoUsers, jsonResponse, renderWithProviders } from './testUtils'

function meAndEmptyWorkflows(user: (typeof demoUsers)[keyof typeof demoUsers]) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/auth/me')) return jsonResponse(user)
    return jsonResponse({ workflows: [], total: 0, limit: 50, offset: 0 })
  })
}

describe('authenticated navigation by role', () => {
  beforeEach(() => {
    setStoredToken('token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setStoredToken(null)
  })

  it('employee sidebar', async () => {
    vi.stubGlobal('fetch', meAndEmptyWorkflows(demoUsers.employee))
    renderWithProviders(<App />, { route: '/dashboard', token: 'token' })
    expect(await screen.findByRole('button', { name: /log out/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /my leave/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /my requests/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /approvals/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /employees/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /user management/i })).not.toBeInTheDocument()
  }, 15000)

  it('manager sidebar', async () => {
    vi.stubGlobal('fetch', meAndEmptyWorkflows(demoUsers.manager))
    renderWithProviders(<App />, { route: '/dashboard', token: 'token' })
    expect(await screen.findByRole('button', { name: /log out/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /approvals/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /recruitment/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^audit$/i })).not.toBeInTheDocument()
  }, 15000)

  it('hr sidebar', async () => {
    vi.stubGlobal('fetch', meAndEmptyWorkflows(demoUsers.hr))
    renderWithProviders(<App />, { route: '/dashboard', token: 'token' })
    expect(await screen.findByRole('button', { name: /log out/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /employees/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^audit$/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /offboarding/i })).toBeInTheDocument()
  }, 15000)

  it('admin sidebar', async () => {
    vi.stubGlobal('fetch', meAndEmptyWorkflows(demoUsers.admin))
    renderWithProviders(<App />, { route: '/dashboard', token: 'token' })
    expect(await screen.findByRole('button', { name: /log out/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /settings/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /approvals/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /employees/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /user management/i })).toBeInTheDocument()
  }, 15000)
})
