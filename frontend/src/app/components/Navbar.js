'use client'
import { useEffect, useState, useSyncExternalStore } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname, useRouter } from 'next/navigation'
import { Icon } from './Icons'
import {
  getServerSessionSnapshot,
  getSessionSnapshot,
  hydrateSession,
  logout,
  subscribeAuth,
} from '@/lib/auth'

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/longitudinal', label: 'Longitudinal' },
  { href: '/patient', label: 'Patient Portal' },
  { href: '/admin', label: 'Clinical Workspace' },
]

export default function Navbar() {
  const pathname = usePathname()
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const session = useSyncExternalStore(
    subscribeAuth,
    getSessionSnapshot,
    getServerSessionSnapshot
  )

  useEffect(() => {
    hydrateSession().catch(() => {})
  }, [])

  const handleLogout = async () => {
    setMenuOpen(false)
    await logout()
    router.push('/login?loggedOut=1')
  }

  const initials = session?.fullName
    ? session.fullName.split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase()
    : 'WS'

  return (
    <header className="app-nav-wrap">
      <nav className="app-nav" aria-label="Primary">
        <Link href="/" className="brand" onClick={() => setMenuOpen(false)}>
          <span className="brand-mark" aria-hidden="true">
            <Image src="/wound-splat-logo.png" alt="" fill sizes="38px" priority />
          </span>
          <span className="brand-name">Wound-Splat</span>
        </Link>

        <div className="nav-links">
          <span className="nav-clinic">Metro Care Clinic</span>
          {NAV_ITEMS.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${pathname === item.href ? 'active' : ''}`}
            >
              {item.label}
            </Link>
          ))}

          <div className="nav-auth">
            {session ? (
              <>
                <Link href="/dashboard" className="nav-user" title={`${session.fullName} (${session.role})`}>
                  <span className="nav-user-avatar">{initials}</span>
                  <span>{session.fullName}</span>
                </Link>
                <button type="button" className="nav-logout" onClick={handleLogout}>
                  <Icon name="logout" size={14} />
                  <span>Log out</span>
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className={`nav-link ${pathname === '/login' ? 'active' : ''}`}>
                  Sign in
                </Link>
                <Link href="/signup" className="btn btn-primary nav-signup-btn">
                  Sign up
                </Link>
              </>
            )}
          </div>
        </div>

        <button
          type="button"
          className="nav-menu-btn"
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(prev => !prev)}
        >
          <Icon name={menuOpen ? 'close' : 'menu'} size={20} />
        </button>
      </nav>

      {menuOpen && (
        <div className="mobile-nav-drawer" aria-label="Mobile navigation">
          {NAV_ITEMS.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`mobile-nav-link ${pathname === item.href ? 'active' : ''}`}
              onClick={() => setMenuOpen(false)}
            >
              {item.label}
            </Link>
          ))}
          <div className="mobile-nav-divider" />
          {session ? (
            <div className="mobile-nav-auth">
              <Link href="/dashboard" className="nav-user" onClick={() => setMenuOpen(false)}>
                <span className="nav-user-avatar">{initials}</span>
                <span>{session.fullName}</span>
              </Link>
              <button type="button" className="btn btn-secondary" onClick={handleLogout}>
                <Icon name="logout" size={15} />
                Log out
              </button>
            </div>
          ) : (
            <div className="mobile-nav-auth">
              <Link href="/login" className="btn btn-secondary" onClick={() => setMenuOpen(false)}>
                Sign in
              </Link>
              <Link href="/signup" className="btn btn-primary" onClick={() => setMenuOpen(false)}>
                Sign up
              </Link>
            </div>
          )}
        </div>
      )}
    </header>
  )
}
