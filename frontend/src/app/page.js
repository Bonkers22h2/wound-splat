import Link from 'next/link'
import Navbar from './components/Navbar'

export default function Home() {
  return (
    <>
      <Navbar />
      <main style={{ maxWidth: '960px', margin: '0 auto', padding: '4rem 2rem', textAlign: 'center' }}>
        <div style={{ marginBottom: '1rem', color: '#0F6E56', fontWeight: 600, fontSize: '14px', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          3D Wound Monitoring
        </div>
        <h1 style={{ fontSize: '48px', fontWeight: 700, lineHeight: 1.1, marginBottom: '1.5rem', color: '#111827' }}>
          Wound-Splat
        </h1>
        <p style={{ fontSize: '18px', color: '#6b7280', maxWidth: '560px', margin: '0 auto 3rem', lineHeight: 1.6 }}>
          GPU-accelerated 3D reconstruction for diabetic foot ulcer monitoring using smartphone videos and 3D Gaussian Splatting.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link href="/patient" style={{
            background: '#0F6E56',
            color: 'white',
            padding: '14px 32px',
            borderRadius: '8px',
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: '16px'
          }}>
            Patient Portal
          </Link>
          <Link href="/admin" style={{
            background: 'white',
            color: '#0F6E56',
            padding: '14px 32px',
            borderRadius: '8px',
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: '16px',
            border: '2px solid #0F6E56'
          }}>
            Clinical Admin
          </Link>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginTop: '5rem' }}>
          {[
            { icon: '📱', title: 'Smartphone Input', desc: 'Upload wound videos captured with any smartphone. No special hardware required.' },
            { icon: '🧠', title: '3D Reconstruction', desc: 'COLMAP + 3D Gaussian Splatting builds a detailed 3D model of the wound.' },
            { icon: '📊', title: 'Clinical Measurements', desc: 'Automated volume, surface area, and depth measurements saved to patient reports.' }
          ].map((item, i) => (
            <div key={i} style={{ background: 'white', borderRadius: '12px', padding: '2rem', border: '1px solid #e5e7eb', textAlign: 'left' }}>
              <div style={{ fontSize: '32px', marginBottom: '1rem' }}>{item.icon}</div>
              <h3 style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '16px' }}>{item.title}</h3>
              <p style={{ color: '#6b7280', fontSize: '14px', lineHeight: 1.6 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </main>
    </>
  )
}
