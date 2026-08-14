import type { ReactNode } from 'react'
import { BrandMark } from '../Brand'
import { ToastViewport } from '../ui/Primitives'
import { useToast } from '../../context/ToastContext'

export function AuthShell({ children }: { children: ReactNode }) {
  const { toasts, dismiss } = useToast()

  return (
    <div className="login-page">
      <section className="login-hero" aria-label="WorkSphere AI">
        <div>
          <BrandMark size={48} />
          <p className="product-kicker">WorkSphere AI</p>
          <h1>AI-Powered HR Workflow &amp; Decision Automation</h1>
          <p>
            Automate HR workflows with intelligent agents, policy-aware decisions, and
            human oversight.
          </p>
          <ul className="hero-points">
            <li>Specialized agents coordinated as enterprise workflows</li>
            <li>Policy-aware decisions with evidence and confidence</li>
            <li>Human approval, audit trails, and operational control</li>
          </ul>
        </div>
        <p className="hero-footnote">
          Intelligent HR workflows powered by specialized agents, policy-aware decisions,
          human approval, and auditable automation.
        </p>
      </section>
      <section className="login-panel">{children}</section>
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </div>
  )
}
