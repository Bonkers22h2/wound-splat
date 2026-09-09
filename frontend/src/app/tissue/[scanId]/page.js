'use client'
import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import Navbar from '../../components/Navbar'
import { tissueApi, scanUrls } from '@/lib/api'
import { COLORS } from '@/lib/theme'
import BoxSelector from './BoxSelector'
import TissueBreakdown from './TissueBreakdown'

export default function TissuePage() {
  const { scanId } = useParams()
  const [box, setBox] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // Bumped after each analysis so the browser refetches the overlay instead
  // of showing the previous one from cache.
  const [version, setVersion] = useState(0)

  useEffect(() => {
    tissueApi.get(scanId).then((saved) => {
      if (saved) { setResult(saved); setVersion((v) => v + 1) }
    }).catch(() => {})
  }, [scanId])

  const analyse = useCallback(async () => {
    if (!box) return
    setBusy(true)
    setError(null)
    try {
      const response = await tissueApi.analyse(scanId, box)
      const body = await response.json()
      if (!response.ok) {
        setError(body.detail || 'Tissue analysis failed')
        return
      }
      setResult(body)
      setVersion((v) => v + 1)
    } catch {
      setError('Could not reach the server')
    } finally {
      setBusy(false)
    }
  }, [box, scanId])

  return (
    <>
      <Navbar />
      <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
        <Link href={`/viewer/${scanId}`} style={{
          fontSize: '13px', color: COLORS.primary, textDecoration: 'none',
        }}>
          ← Back to 3D model
        </Link>
        <h1 style={{ fontSize: '20px', fontWeight: 700, margin: '0.5rem 0 0.25rem' }}>
          Wound tissue types
        </h1>
        <p style={{ fontSize: '13px', color: COLORS.textMuted, marginTop: 0 }}>
          Drag a box around the wound, then run the analysis.
        </p>

        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 420px' }}>
            <BoxSelector
              src={scanUrls.tissueFrame(scanId)}
              onChange={setBox}
              disabled={busy}
            />
            <p style={{ fontSize: '12px', color: COLORS.textMuted, marginTop: '0.5rem' }}>
              This is the clearest of the opening frames, chosen automatically.
              It is the same photo the model reads.
            </p>
          </div>

          <div style={{ flex: '1 1 320px', minWidth: '300px' }}>
            <div style={{
              padding: '10px 12px', borderRadius: '8px', fontSize: '12px',
              background: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0',
              marginBottom: '1rem', lineHeight: 1.5,
            }}>
              Draw the box <strong>close around the wound</strong>. The model was
              trained on tight wound close-ups and has no way to label plain
              skin, so a loose box makes it over-report callus.
            </div>

            <button
              onClick={analyse}
              disabled={!box || busy}
              style={{
                width: '100%', padding: '10px', borderRadius: '8px',
                fontWeight: 600, fontSize: '14px', marginBottom: '1rem',
                border: `1px solid ${COLORS.primary}`,
                background: box && !busy ? COLORS.primary : '#f3f4f6',
                color: box && !busy ? 'white' : COLORS.textMuted,
                cursor: !box || busy ? 'not-allowed' : 'pointer',
              }}
            >
              {busy ? 'Analysing…' : box ? 'Analyse tissue' : 'Draw a box first'}
            </button>

            {error && (
              <div style={{
                padding: '10px 12px', borderRadius: '8px', fontSize: '13px',
                background: '#fee2e2', color: '#991b1b',
                border: '1px solid #fecaca', marginBottom: '1rem',
              }}>
                {error}
              </div>
            )}

            <TissueBreakdown result={result} />

            {result && !result.no_wound_detected && (
              <div style={{ marginTop: '1rem' }}>
                <p style={{
                  fontSize: '11px', fontWeight: 700, color: COLORS.primary,
                  textTransform: 'uppercase', letterSpacing: '0.08em',
                }}>
                  Labelled wound
                </p>
                <img
                  src={scanUrls.tissueOverlay(scanId, version)}
                  alt="The selected wound area with tissue types coloured in"
                  style={{ maxWidth: '100%', borderRadius: '8px' }}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
