'use client'
import Link from 'next/link'
import Navbar from './components/Navbar'

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <section className="home-shell">
          <div>
            <div className="home-kicker"><span>Clinical 3D wound monitoring</span></div>
            <h1 className="home-title">Precise wound care, from every angle.</h1>
            <p className="home-copy">
              Capture, reconstruct, and review wound models with calibrated measurements,
              tissue analysis, and a complete longitudinal scan history.
            </p>
            <div className="home-actions">
              <Link href="/login" className="btn btn-primary" style={{ minHeight:'48px', padding:'11px 20px' }}>
                Sign in
              </Link>
              <Link href="/dashboard" className="btn btn-secondary" style={{ minHeight:'48px', padding:'11px 20px' }}>
                Open dashboard
              </Link>
              <Link href="/patient" className="btn btn-secondary" style={{ minHeight:'48px', padding:'11px 20px' }}>
                Patient portal
              </Link>
            </div>
            <details style={{ marginTop:'18px', maxWidth:'610px' }}>
              <summary style={{ cursor:'pointer', color:'#176B61', fontSize:'12px', fontWeight:750 }}>
                Preview the full prototype
              </summary>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(2,minmax(0,1fr))', gap:'8px', marginTop:'10px' }}>
                <Link className="btn btn-secondary" href="/login">Sign in</Link>
                <Link className="btn btn-secondary" href="/signup">Create account</Link>
                <Link className="btn btn-secondary" href="/dashboard">Summary dashboard</Link>
                <Link className="btn btn-secondary" href="/patient">Patient experience</Link>
                <Link className="btn btn-secondary" href="/admin">Clinical workspace</Link>
                <Link className="btn btn-secondary" href="/viewer/demo-scan-001">3D wound viewer</Link>
                <Link className="btn btn-secondary" href="/tissue/demo-scan-001">Tissue analysis</Link>
                <Link className="btn btn-secondary" href="/longitudinal">Longitudinal review</Link>
              </div>
            </details>
            <div className="home-feature-row">
              {[
                ['01','Smartphone capture','Guided recording using a known-size reference.'],
                ['02','3D reconstruction','Turn video frames into a calibrated wound model.'],
                ['03','Clinical review','Measure, compare, and document healing over time.'],
              ].map(([number,title,description]) => (
                <div className="home-feature" key={number}>
                  <span className="home-feature-number">{number}</span>
                  <div><h3>{title}</h3><p>{description}</p></div>
                </div>
              ))}
            </div>
          </div>
          <div className="home-preview" aria-label="Preview of the 3D wound review workspace">
            <div className="home-preview-grid" />
            <div className="home-preview-model" />
            <div style={{ position:'absolute', top:'18px', right:'18px' }} className="status status-rendered">
              Model rendered
            </div>
            <div className="home-preview-panel">
              <strong>Scan summary</strong>
              <span>Surface area&nbsp;&nbsp; 18.42 cm²</span>
              <span>Volume&nbsp;&nbsp; 7.68 cm³</span>
              <span>Registration&nbsp;&nbsp; 91%</span>
            </div>
            <div style={{ position:'absolute', bottom:'18px', left:'18px', color:'#71817D', fontSize:'11px' }}>
              Wound-Splat · 3D reconstruction
            </div>
          </div>
        </section>
      </main>
    </>
  )
}
