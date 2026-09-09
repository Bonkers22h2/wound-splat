'use client'
import { COLORS } from '@/lib/theme'

// Same colours as the overlay the model produces, which come from the
// dataset's own palette file: red - fibrin, green - granulation, blue - callus.
const TISSUES = [
  { key: 'granulation', label: 'Granulation', colour: 'rgb(40,190,60)',
    note: 'healthy healing tissue' },
  { key: 'fibrin', label: 'Fibrin', colour: 'rgb(220,40,40)',
    note: 'yellow slough' },
  { key: 'callus', label: 'Callus', colour: 'rgb(50,90,220)',
    note: 'thickened skin at the edge' },
]

export default function TissueBreakdown({ result }) {
  if (!result) return null

  if (result.no_wound_detected) {
    return (
      <div style={{
        padding: '12px 14px', borderRadius: '8px', fontSize: '13px',
        background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a',
      }}>
        <strong>No wound found in that box.</strong>
        <p style={{ margin: '6px 0 0' }}>
          Less than 1% of the selection looked like wound tissue, so no
          percentages are shown — they would be based on a handful of pixels.
          Try drawing the box around the wound itself.
        </p>
      </div>
    )
  }

  const woundShare = result.wound_fraction_of_box

  return (
    <div>
      {TISSUES.map(({ key, label, colour, note }) => {
        const value = result.percentages?.[key] ?? 0
        return (
          <div key={key} style={{ marginBottom: '14px' }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              alignItems: 'baseline', marginBottom: '4px',
            }}>
              <span style={{ fontSize: '13px', fontWeight: 600 }}>{label}</span>
              <span style={{ fontSize: '15px', fontWeight: 700 }}>
                {value.toFixed(1)}%
              </span>
            </div>
            <div style={{
              height: '8px', borderRadius: '999px',
              background: '#f3f4f6', overflow: 'hidden',
            }}>
              <div style={{
                width: `${value}%`, height: '100%', background: colour,
                borderRadius: '999px',
              }} />
            </div>
            <span style={{ fontSize: '11px', color: COLORS.textMuted }}>{note}</span>
          </div>
        )
      })}

      <p style={{
        marginTop: '1rem', fontSize: '12px', lineHeight: 1.5,
        color: COLORS.textMuted, borderTop: `1px solid ${COLORS.border}`,
        paddingTop: '0.75rem',
      }}>
        Percentages are shares of the wound only, so they total 100% and do
        not change with how large the box is drawn.
        {woundShare != null && (
          <> The model called <strong>{(woundShare * 100).toFixed(0)}%</strong> of
          the box wound tissue; that figure does depend on the box, so draw it
          close around the wound.</>
        )}
      </p>
    </div>
  )
}
