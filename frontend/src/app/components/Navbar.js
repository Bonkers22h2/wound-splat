'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function Navbar() {
  const pathname = usePathname()

  return (
    <nav style={{
      background: '#0F6E56',
      padding: '0 2rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: '56px',
      position: 'sticky',
      top: 0,
      zIndex: 100
    }}>
      <Link href="/" style={{ color: 'white', fontWeight: 700, fontSize: '18px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '20px' }}>⚕</span> Wound-Splat
      </Link>
      <div style={{ display: 'flex', gap: '8px' }}>
        <Link href="/patient" style={{
          color: 'white',
          textDecoration: 'none',
          padding: '6px 16px',
          borderRadius: '6px',
          fontSize: '14px',
          background: pathname === '/patient' ? 'rgba(255,255,255,0.2)' : 'transparent'
        }}>
          Patient Portal
        </Link>
        <Link href="/admin" style={{
          color: 'white',
          textDecoration: 'none',
          padding: '6px 16px',
          borderRadius: '6px',
          fontSize: '14px',
          background: pathname === '/admin' ? 'rgba(255,255,255,0.2)' : 'transparent'
        }}>
          Clinical Admin
        </Link>
      </div>
    </nav>
  )
}
