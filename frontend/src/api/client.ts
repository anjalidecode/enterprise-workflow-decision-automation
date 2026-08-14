import type { APIError } from '../types/api'

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string
  readonly details: Record<string, unknown>

  constructor(
    status: number,
    code: string,
    message: string,
    requestId = '',
    details: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
  }
}

const TOKEN_KEY = 'ewda_access_token'

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token: string | null, remember = true): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_KEY)
    if (token) {
      const store = remember ? localStorage : sessionStorage
      store.setItem(TOKEN_KEY, token)
    }
  } catch {
    // ignore storage failures in restricted environments
  }
}

export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  return (raw || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')
}

type RequestOptions = {
  method?: string
  body?: unknown
  token?: string | null
  signal?: AbortSignal
}

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

async function parseError(response: Response): Promise<ApiClientError> {
  let code = `HTTP_${response.status}`
  let message = response.statusText || 'Request failed'
  let requestId = response.headers.get('X-Request-ID') || ''
  let details: Record<string, unknown> = {}

  try {
    const data = (await response.json()) as APIError
    if (data?.error) {
      code = data.error.code || code
      message = data.error.message || message
      requestId = data.error.request_id || requestId
      details = data.error.details || {}
    }
  } catch {
    // non-JSON error body
  }

  if (response.status === 401) {
    code = code || 'AUTHENTICATION_REQUIRED'
    message = message || 'Authentication is required.'
  } else if (response.status === 403) {
    code = code || 'FORBIDDEN'
    message = message || 'You do not have permission to perform this action.'
  } else if (response.status === 404) {
    code = code || 'NOT_FOUND'
  } else if (response.status === 422) {
    code = code || 'VALIDATION_ERROR'
    message = message || 'Validation failed.'
  } else if (response.status >= 500) {
    code = code || 'SERVER_ERROR'
    message = message || 'The server encountered an error.'
  }

  return new ApiClientError(response.status, code, message, requestId, details)
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const base = getApiBaseUrl()
  const url = path.startsWith('http') ? path : `${base}${path.startsWith('/') ? '' : '/'}${path}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  const token = options.token === undefined ? getStoredToken() : options.token
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let body: string | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body,
      signal: options.signal,
    })
  } catch {
    throw new ApiClientError(
      0,
      'NETWORK_ERROR',
      'Unable to reach the API. Check that the backend is running and VITE_API_BASE_URL is correct.',
    )
  }

  if (response.status === 401) {
    onUnauthorized?.()
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
