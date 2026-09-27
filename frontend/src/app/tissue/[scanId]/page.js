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
  const [box, setBox] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [interacting, setInteracting] = useState(false)
  const [error, setError] = useState(null)
  const [version, setVersion] = useState(0)
  const edited = useRef(false)
  const inFlight = useRef(false)
  const matches = box && result?.box && ['left', 'top', 'right', 'bottom'].every((key) => box[key] === result.box[key])

  useEffect(() => {
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
    <main style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <Link href={`/viewer/${scanId}`} style={{ fontSize: '13px', color: COLORS.primary }}>← Back to 3D model</Link>
      <h1 style={{ fontSize: '24px', fontWeight: 700, margin: '0.75rem 0 0.25rem' }}>Wound tissue types</h1>
      <p style={{ fontSize: '14px', color: COLORS.textMuted, marginBottom: '1.5rem' }}>Select the wound, check the close-up, then analyse the tissue.</p>
      <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 480px', minWidth: 0 }}>
          <BoxSelector src={scanUrls.tissueFrame(scanId)} box={box} onChange={changeBox}
            disabled={busy || loading} onInteraction={setInteracting} />
          <p style={{ fontSize: '12px', color: COLORS.textMuted, marginTop: '1rem' }}>This photo is selected automatically from the opening frames. It is the same photo used for analysis.</p>
        </div>
        <section style={{ flex: '1 1 300px', minWidth: 0, borderTop: `3px solid ${COLORS.primary}`, paddingTop: '1rem' }} aria-busy={busy}>
          <h2 style={{ fontSize: '16px', fontWeight: 650, margin: '0 0 10px' }}>3. Analyse tissue</h2>
          <p style={{ fontSize: '13px', lineHeight: 1.6, color: COLORS.textMuted }}>A close selection helps keep unrelated skin and objects out of the analysis. Changing the selected area can change the tissue percentages.</p>
          <button onClick={analyse} disabled={!canAnalyse} style={{
            width: '100%', padding: '12px', borderRadius: '8px', fontWeight: 600, fontSize: '14px',
            border: `1px solid ${COLORS.primary}`, background: canAnalyse ? COLORS.primary : '#f3f4f6',
            color: canAnalyse ? 'white' : COLORS.textMuted, cursor: canAnalyse ? 'pointer' : 'not-allowed',
          }}>{loading ? 'Loading saved result…' : busy ? 'Analysing…' : box ? 'Analyse tissue' : 'Select the wound first'}</button>
          <p role="status" style={{ fontSize: '13px', lineHeight: 1.6, color: matches ? COLORS.primary : '#92400e', margin: '16px 0' }}>
            {busy ? 'Analysing the selected area. Please keep this page open.' : result
              ? matches ? 'Showing the saved result for this selection.' : 'Previous result: the selection has changed. Analyse again to update the results and report.'
              : 'Check the close-up before starting your first analysis.'}
          </p>
          {error && <p role="alert" style={{ padding: '12px', borderRadius: '8px', fontSize: '13px', background: '#fee2e2', color: '#991b1b' }}>{error}</p>}
          <TissueBreakdown result={result} />
          {result && !result.no_wound_detected && <div style={{ marginTop: '1rem' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 650 }}>{matches ? 'Labelled wound' : 'Previously labelled wound'}</h3>
            <img src={scanUrls.tissueOverlay(scanId, version)} alt="Tissue overlay from the last completed analysis" style={{ maxWidth: '100%', borderRadius: '8px' }} />
          </div>}
        </section>
      </div>
    </main>
  </>
}
