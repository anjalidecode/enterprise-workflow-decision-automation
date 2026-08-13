import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { LoadingBlock } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import type { Role } from '../types/api'

export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { isAuthenticated, loading, user } = useAuth()
  const location = useLocation()

  if (loading) {
    return <LoadingBlock label="Checking session…" />
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}

export function PublicOnlyRoute() {
  const { isAuthenticated, loading } = useAuth()
  if (loading) {
    return <LoadingBlock label="Loading…" />
  }
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }
  return <Outlet />
}
