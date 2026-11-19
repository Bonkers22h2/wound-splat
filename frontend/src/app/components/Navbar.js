'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="app-nav">
      <Link href="/" className="brand">
        <span className="brand-mark" aria-hidden="true">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none">
            <path d="M12 3.5c1.6 3.2 5 5.2 5 9.3a5 5 0 0 1-10 0c0-4.1 3.4-6.1 5-9.3Z" stroke="currentColor" strokeWidth="1.8"/>
            <path d="M9.2 14.2c1.2 1.5 4.4 1.5 5.6 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
        </span>
        <span className="brand-name">Wound-Splat</span>
      </Link>
      <div className="nav-links">
        <span className="nav-clinic">Metro Care Clinic</span>
        <Link href="/patient" className={`nav-link ${pathname === '/patient' ? 'active' : ''}`}>
          Patient Portal
        </Link>
        <Link href="/admin" className={`nav-link ${pathname === '/admin' ? 'active' : ''}`}>
          Clinical Workspace
        </Link>
      </div>
    </nav>
  )
}
