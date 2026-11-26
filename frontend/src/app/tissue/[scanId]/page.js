'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import Navbar from '../../components/Navbar'
import { tissueApi, scanUrls } from '@/lib/api'
import { COLORS } from '@/lib/theme'
import BoxSelector from './BoxSelector'
import TissueBreakdown from './TissueBreakdown'

export default function TissuePage() {
  const { scanId } = useParams()
  return <TissueSelection key={scanId} scanId={scanId} />
}

function TissueSelection({ scanId }) {
  const demoMode = String(scanId).startsWith('demo-')
  const [box, setBox] = useState(demoMode ? { left:120, top:90, right:420, bottom:390 } : null)
  const [result, setResult] = useState(demoMode ? {
    no_wound_detected:false,
    percentages:{ granulation:58.4, fibrin:25.8, callus:15.8 },
    wound_fraction_of_box:.92,
    box:{ left:120, top:90, right:420, bottom:390 },
  } : null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(!demoMode)
  const [interacting, setInteracting] = useState(false)
  const [error, setError] = useState(null)
  const [version, setVersion] = useState(0)
  const edited = useRef(false)
  const inFlight = useRef(false)
  const matches = box && result?.box && ['left', 'top', 'right', 'bottom'].every((key) => box[key] === result.box[key])

  useEffect(() => {
    if (demoMode) return
    let active = true
    tissueApi.get(scanId).then((saved) => {
      if (!active || !saved) return
      setResult(saved)
      if (!edited.current) setBox(saved.box)
      setVersion((v) => v + 1)
    }).catch(() => {
      if (active) setError('Could not load the saved result. Check your connection and reload the page.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [scanId])

  const changeBox = useCallback((next) => {
    edited.current = true
    setBox(next)
  }, [])

  const analyse = useCallback(async () => {
    if (!box || busy || loading || interacting || inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      const response = await tissueApi.analyse(scanId, box)
      const body = await response.json()
      if (!response.ok) {
        setError(typeof body.detail === 'string' ? body.detail : 'Tissue analysis failed. Please try again.')
        return
      }
      setResult(body)
      setVersion((v) => v + 1)
    } catch {
      setError('Could not complete the analysis. Check your connection and try again.')
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }, [box, busy, loading, interacting, scanId])
  const canAnalyse = box && !busy && !loading && !interacting

  return <>
    <Navbar />
    <main className="page">
      <div className="page-container">
      <Link href={`/viewer/${scanId}`} style={{ fontSize:'13px', color:'#0F766E', textDecoration:'none', fontWeight:700 }}>← Back to 3D model</Link>
      <div className="page-header" style={{ marginTop:'12px', marginBottom:'18px' }}>
        <div><div className="eyebrow">Scan review</div><h1 className="page-title">Wound tissue analysis</h1><p className="page-subtitle">Select the wound area and validate the tissue breakdown.</p></div>
        {result && <span className={`status ${result.no_wound_detected?'status-failed':'status-calibrated'}`}>{result.no_wound_detected?'No wound detected':'Analysis complete'}</span>}
      </div>
      <div className="tissue-layout">
        {demoMode ? (
          <div className="card" style={{ padding:'12px' }}>
            <div style={{ position:'relative', height:'430px', borderRadius:'10px', overflow:'hidden', background:'linear-gradient(135deg,#E7ECF0,#F8FAFC)' }}>
              <div style={{ position:'absolute', left:'18%', top:'20%', width:'64%', height:'60%', border:'2px solid #10B981', borderRadius:'50%', background:'radial-gradient(circle,#10B981 0 18%,#F59E0B 19% 43%,#3B82F6 44% 49%,rgba(59,130,246,.35) 50% 68%,rgba(16,185,129,.12) 69%)', boxShadow:'0 18px 40px rgba(15,23,42,.12)' }}>
                {['nw','ne','sw','se'].map(corner => (
                  <span key={corner} style={{ position:'absolute', width:'14px', height:'14px', borderRadius:'50%', border:'2px solid white', background:'#0F766E', top:corner.includes('n')?'-7px':'auto', bottom:corner.includes('s')?'-7px':'auto', left:corner.includes('w')?'-7px':'auto', right:corner.includes('e')?'-7px':'auto' }} />
                ))}
              </div>
              <div style={{ position:'absolute', right:'16px', bottom:'16px', background:'rgba(255,255,255,.92)', border:'1px solid #E2E8F0', borderRadius:'8px', padding:'8px 10px', fontSize:'11px', color:'#475569' }}>Demo wound frame</div>
            </div>
            <p className="helper" style={{ padding:'10px 4px 2px' }}>Demo mode · a representative wound frame with a selectable tissue area.</p>
          </div>
        ) : (
          <div className="card" style={{ padding:'12px' }}>
            <BoxSelector src={scanUrls.tissueFrame(scanId)} box={box} onChange={changeBox}
              disabled={busy || loading} onInteraction={setInteracting} />
            <p className="helper" style={{ padding:'10px 4px 2px' }}>The selected frame is the same frame used for tissue analysis.</p>
          </div>
        )}
        <section className="tissue-panel" aria-busy={busy}>
          <h2 className="card-title" style={{ marginBottom:'8px' }}>Analysis controls</h2>
          <p className="helper">Keep the selection close to the wound to exclude healthy skin and reference objects.</p>
          <button onClick={analyse} disabled={!canAnalyse} style={{
            width:'100%', marginTop:'14px', padding:'11px', borderRadius:'9px', fontWeight:750, fontSize:'13px',
            border:'1px solid #0F766E', background:canAnalyse?'#0F766E':'#F1F5F9',
            color:canAnalyse?'white':'#94A3B8', cursor:canAnalyse?'pointer':'not-allowed',
          }}>{loading ? 'Loading saved result…' : busy ? 'Analysing…' : box ? 'Analyse tissue' : 'Select the wound first'}</button>
          <p role="status" className="helper" style={{ color:matches?'#166534':'#92400E', margin:'14px 0' }}>
            {busy ? 'Analysing the selected area. Please keep this page open.' : result
              ? matches ? 'Showing the saved result for this selection.' : 'Previous result: the selection has changed. Analyse again to update the results and report.'
              : 'Check the close-up before starting your first analysis.'}
          </p>
          {error && <p role="alert" className="notice notice-error">{error}</p>}
          <TissueBreakdown result={result} />
          {result && !result.no_wound_detected && <div style={{ marginTop: '1rem' }}>
            <h3 style={{ fontSize:'13px', marginBottom:'8px' }}>{matches?'Labelled wound':'Previously labelled wound'}</h3>
            <img src={scanUrls.tissueOverlay(scanId, version)} alt="Tissue overlay from the last completed analysis" style={{ maxWidth: '100%', borderRadius: '8px' }} />
          </div>}
        </section>
      </div>
      </div>
    </main>
  </>
}
