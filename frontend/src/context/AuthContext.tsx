import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { authApi } from '../api'
import {
  ApiClientError,
  getStoredToken,
  setStoredToken,
  setUnauthorizedHandler,
} from '../api/client'
import type { User } from '../types/api'

type AuthContextValue = {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => getStoredToken())
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    setStoredToken(null)
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setStoredToken(null)
      setToken(null)
      setUser(null)
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      const existing = getStoredToken()
      if (!existing) {
        if (!cancelled) {
          setLoading(false)
          setUser(null)
          setToken(null)
        }
        return
      }
      try {
        const me = await authApi.me(existing)
        if (!cancelled) {
          setToken(existing)
          setUser(me)
        }
      } catch {
        if (!cancelled) {
          setStoredToken(null)
          setToken(null)
          setUser(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const result = await authApi.login({ username, password })
    setStoredToken(result.access_token)
    setToken(result.access_token)
    setUser(result.user)
  }, [])

  const refreshUser = useCallback(async () => {
    const current = getStoredToken()
    if (!current) {
      logout()
      return
    }
    try {
      const me = await authApi.me(current)
      setUser(me)
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 401) {
        logout()
      }
      throw err
    }
  }, [logout])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token && user),
      loading,
      login,
      logout,
      refreshUser,
    }),
    [user, token, loading, login, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
