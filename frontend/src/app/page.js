'use client'
import Link from 'next/link'
import Navbar from './components/Navbar'

export default function Home() {
  return (
    <>
      <Navbar />
      <main className="page">
        <section className="page-container" style={{ minHeight:'calc(100vh - 132px)', display:'flex', alignItems:'center' }}>
          <div style={{ width:'100%' }}>
            <div style={{ display:'grid', gridTemplateColumns:'minmax(0,1.05fr) minmax(360px,.95fr)', gap:'56px', alignItems:'center' }}>
              <div>
                <div className="eyebrow">Clinical 3D wound monitoring</div>
                <h1 style={{ maxWidth:'720px', fontSize:'clamp(44px,5vw,68px)', lineHeight:'1.02', letterSpacing:'-.055em', fontWeight:760, marginBottom:'22px' }}>
                  Precise wound care,<br />from every angle.
                </h1>
                <p style={{ maxWidth:'610px', color:'#475569', fontSize:'18px', lineHeight:'1.7', marginBottom:'32px' }}>
                  Capture, reconstruct, and review wound models with calibrated measurements,
                  tissue analysis, and a complete longitudinal scan history.
                </p>
                <div style={{ display:'flex', gap:'10px', flexWrap:'wrap' }}>
                  <Link href="/patient" className="btn btn-primary" style={{ minHeight:'48px', padding:'11px 20px' }}>
                    Continue as patient
                  </Link>
                  <Link href="/admin" className="btn btn-secondary" style={{ minHeight:'48px', padding:'11px 20px' }}>
                    Open clinical workspace
                  </Link>
                </div>
                <details style={{ marginTop:'18px', maxWidth:'610px' }}>
                  <summary style={{ cursor:'pointer', color:'#0F766E', fontSize:'13px', fontWeight:750 }}>Preview every screen without the backend</summary>
                  <div style={{ display:'grid', gridTemplateColumns:'repeat(2,minmax(0,1fr))', gap:'8px', marginTop:'10px' }}>
                    <Link className="btn btn-secondary" href="/patient">Patient sign-in and dashboard</Link>
                    <Link className="btn btn-secondary" href="/admin">Clinical dashboard</Link>
                    <Link className="btn btn-secondary" href="/viewer/demo-scan-001">3D wound viewer</Link>
                    <Link className="btn btn-secondary" href="/tissue/demo-scan-001">Tissue analysis</Link>
                  </div>
                </details>
                <div style={{ display:'flex', gap:'22px', marginTop:'36px', color:'#64748B', fontSize:'12px' }}>
                  <span>Calibrated measurement support</span>
                  <span>Secure clinical review</span>
                </div>
              </div>

              <div className="card" style={{ overflow:'hidden', boxShadow:'0 24px 60px rgba(15,23,42,.10)' }}>
                <div style={{ height:'410px', position:'relative', overflow:'hidden', background:'radial-gradient(circle at 48% 48%,#1E293B 0,#111827 48%,#030712 100%)' }}>
                  <div style={{ position:'absolute', inset:0, backgroundImage:'linear-gradient(rgba(30,41,59,.22) 1px,transparent 1px),linear-gradient(90deg,rgba(30,41,59,.22) 1px,transparent 1px)', backgroundSize:'40px 40px', transform:'perspective(500px) rotateX(58deg) scale(1.35)', transformOrigin:'bottom' }} />
                  <div style={{ position:'absolute', left:'50%', top:'51%', width:'180px', height:'180px', transform:'translate(-50%,-50%)', borderRadius:'50%', background:'radial-gradient(circle,#10B981 0 18%,#F59E0B 19% 42%,#991B1B 43% 48%,rgba(16,185,129,.18) 49% 70%,transparent 71%)', boxShadow:'0 0 44px rgba(16,185,129,.22)' }} />
                  <div style={{ position:'absolute', top:'16px', right:'16px' }} className="status status-rendered">Model rendered</div>
                  <div style={{ position:'absolute', bottom:'14px', left:'14px', right:'14px', display:'flex', justifyContent:'space-between', color:'#CBD5E1', fontSize:'11px' }}>
                    <span>3DGS reconstruction</span><span>Drag · Zoom · Rotate</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid-3" style={{ marginTop:'56px' }}>
              {[
                ['01','Smartphone capture','Record a guided wound scan using an ordinary smartphone and a known-size reference.'],
                ['02','3D reconstruction','Turn the capture into a wound model through COLMAP and Gaussian Splatting processing.'],
                ['03','Clinical review','Inspect tissue composition, track healing, and generate a review-ready report.'],
              ].map(([number,title,description]) => (
                <div key={number} style={{ display:'flex', gap:'14px', padding:'18px 8px 18px 0' }}>
                  <span style={{ color:'#0F766E', fontSize:'12px', fontWeight:800 }}>{number}</span>
                  <div><h3 style={{ fontSize:'15px', marginBottom:'6px' }}>{title}</h3><p style={{ color:'#64748B', fontSize:'13px', lineHeight:'1.6' }}>{description}</p></div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </>
  )
}
