export function BrandMark({ size = 36 }: { size?: number }) {
  return (
    <svg
      className="brand-logo"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-hidden
      focusable="false"
    >
      <rect width="48" height="48" rx="10" fill="#0F1C2E" />
      <circle cx="24" cy="24" r="11" fill="none" stroke="#14B8A6" strokeWidth="2.4" />
      <circle cx="24" cy="24" r="3.2" fill="#5B7CFA" />
      <path
        d="M24 13v4.5M24 30.5V35M13 24h4.5M30.5 24H35"
        stroke="#CCFBF1"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function BrandWordmark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <BrandMark size={compact ? 32 : 40} />
      <div className="brand-text">
        <div className="brand-name">WorkSphere AI</div>
        {compact ? null : (
          <div className="brand-org">HR Workflow &amp; Decision Automation</div>
        )}
      </div>
    </div>
  )
}
