'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="app-nav">
      <Link href="/" className="brand">
        <span className="brand-mark" aria-hidden="true">WS</span>
        <span>Wound-Splat</span>
      </Link>
      <div className="nav-links">
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
