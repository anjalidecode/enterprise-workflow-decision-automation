import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { apiRequest, ApiClientError, getStoredToken, setStoredToken } from '../api/client'
import { jsonResponse } from './testUtils'

describe('api client', () => {
  beforeEach(() => {
    setStoredToken(null)
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setStoredToken(null)
  })

  it('attaches Authorization bearer token', async () => {
    setStoredToken('tok-123')
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiRequest<{ ok: boolean }>('/workflows')

    expect(fetchMock).toHaveBeenCalledOnce()
    const [, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit | undefined]
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer tok-123')
  })

  it('maps 401 errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          { error: { code: 'AUTHENTICATION_REQUIRED', message: 'Auth required' } },
          401,
        ),
      ),
    )

    await expect(apiRequest('/auth/me')).rejects.toMatchObject({
      status: 401,
      code: 'AUTHENTICATION_REQUIRED',
    })
  })

  it('maps 403 and 404 and 422', async () => {
    const cases: Array<[number, string]> = [
      [403, 'FORBIDDEN'],
      [404, 'NOT_FOUND'],
      [422, 'VALIDATION_ERROR'],
    ]
    for (const [status, code] of cases) {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => jsonResponse({ error: { code, message: code } }, status)),
      )
      await expect(apiRequest('/x')).rejects.toBeInstanceOf(ApiClientError)
    }
  })

  it('maps network failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    await expect(apiRequest('/health')).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
    })
  })

  it('stores tokens in localStorage', () => {
    setStoredToken('abc')
    expect(getStoredToken()).toBe('abc')
    setStoredToken(null)
    expect(getStoredToken()).toBeNull()
  })
})
