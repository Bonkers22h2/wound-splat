'use client'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'

export default function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="app-nav">
      <Link href="/" className="brand">
        <span className="brand-mark" aria-hidden="true">
          <Image src="/wound-splat-logo.png" alt="" fill sizes="38px" priority />
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
