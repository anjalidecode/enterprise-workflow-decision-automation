import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement, ReactNode } from 'react'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'
import type { User } from '../types/api'
import { setStoredToken } from '../api/client'

export const demoUsers: Record<string, User> = {
  employee: {
    user_id: 'u-employee',
    username: 'employee001',
    organization_id: 'demo-org',
    role: 'employee',
    employee_id: 'E001',
  },
  manager: {
    user_id: 'u-manager',
    username: 'manager001',
    organization_id: 'demo-org',
    role: 'manager',
    employee_id: 'E100',
  },
  hr: {
    user_id: 'u-hr',
    username: 'hr001',
    organization_id: 'demo-org',
    role: 'hr',
    employee_id: null,
  },
  admin: {
    user_id: 'u-admin',
    username: 'admin001',
    organization_id: 'demo-org',
    role: 'admin',
    employee_id: null,
  },
}

export function mockFetchSequence(
  handlers: Array<(url: string, init?: RequestInit) => Response | Promise<Response>>,
) {
  let index = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const handler = handlers[index]
      index += 1
      if (!handler) {
        throw new Error(`Unexpected fetch: ${url}`)
      }
      return handler(url, init)
    }),
  )
}

export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function renderWithProviders(
  ui: ReactElement,
  options?: { route?: string; token?: string | null },
) {
  setStoredToken(options?.token ?? null)
  const route = options?.route ?? '/'

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </MemoryRouter>
    )
  }

  return render(ui, { wrapper: Wrapper })
}

export function authHeaderOk(user: User) {
  return (url: string) => {
    if (url.includes('/auth/me')) return jsonResponse(user)
    throw new Error(`Unhandled ${url}`)
  }
}
