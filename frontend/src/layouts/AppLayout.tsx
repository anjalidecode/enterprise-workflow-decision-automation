import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { workflowsApi } from '../api'
import { Sidebar } from '../components/layout/Sidebar'
import { Topbar } from '../components/layout/Topbar'
import { ToastViewport } from '../components/ui/Primitives'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { canApprove } from '../utils/rbac'

export function AppLayout() {
  const { user } = useAuth()
  const { toasts, dismiss } = useToast()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [pendingApprovals, setPendingApprovals] = useState(0)

  useEffect(() => {
    if (!user || !canApprove(user.role)) {
      setPendingApprovals(0)
      return
    }
    let cancelled = false
    workflowsApi
      .list({ status: 'awaiting_human_approval', limit: 50 })
      .then((res) => {
        if (!cancelled) setPendingApprovals(res.total)
      })
      .catch(() => {
        if (!cancelled) setPendingApprovals(0)
      })
    return () => {
      cancelled = true
    }
  }, [user])

  return (
    <div className={`app-shell${sidebarOpen ? ' sidebar-open' : ''}`}>
      <Topbar
        pendingApprovals={pendingApprovals}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      <Sidebar open={sidebarOpen} />
      <main className="main-content">
        <Outlet />
      </main>
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </div>
  )
}
