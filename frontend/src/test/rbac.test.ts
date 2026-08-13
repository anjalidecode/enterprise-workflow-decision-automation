import { describe, expect, it } from 'vitest'
import { navForRole, canApprove, canRunWorkflowType } from '../utils/rbac'

describe('role-based navigation', () => {
  it('employee navigation excludes HR administration', () => {
    const paths = navForRole('employee').map((i) => i.to)
    expect(paths).toContain('/dashboard')
    expect(paths).toContain('/leave')
    expect(paths).toContain('/hr-services')
    expect(paths).not.toContain('/approvals')
    expect(paths).not.toContain('/employees')
    expect(paths).not.toContain('/recruitment')
    expect(paths).not.toContain('/offboarding')
    expect(paths).not.toContain('/audit')
  })

  it('manager navigation includes approvals and recruitment', () => {
    const paths = navForRole('manager').map((i) => i.to)
    expect(paths).toContain('/approvals')
    expect(paths).toContain('/recruitment')
    expect(paths).toContain('/performance')
    expect(paths).not.toContain('/employees')
    expect(paths).not.toContain('/audit')
  })

  it('hr navigation includes employees, audit, offboarding', () => {
    const paths = navForRole('hr').map((i) => i.to)
    expect(paths).toContain('/employees')
    expect(paths).toContain('/audit')
    expect(paths).toContain('/offboarding')
    expect(paths).toContain('/approvals')
  })

  it('admin navigation is broad', () => {
    const paths = navForRole('admin').map((i) => i.to)
    expect(paths).toContain('/approvals')
    expect(paths).toContain('/employees')
    expect(paths).toContain('/audit')
    expect(paths).toContain('/settings')
  })

  it('approver roles and employee workflow constraints', () => {
    expect(canApprove('employee')).toBe(false)
    expect(canApprove('manager')).toBe(true)
    expect(canRunWorkflowType('employee', 'recruitment')).toBe(false)
    expect(canRunWorkflowType('employee', 'leave_attendance')).toBe(true)
    expect(canRunWorkflowType('hr', 'offboarding')).toBe(true)
  })
})
