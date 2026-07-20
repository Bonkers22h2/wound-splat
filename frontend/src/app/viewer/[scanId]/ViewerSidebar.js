'use client'
import { scanUrls } from '@/lib/api'
import { COLORS } from '@/lib/theme'

const toggleButtonStyle = (active, busy) => ({
  display: 'block',
  width: '100%',
  background: active ? COLORS.primary : 'white',
  color: active ? 'white' : COLORS.primary,
  padding: '10px',
  borderRadius: '8px',
  textAlign: 'center',
  fontWeight: 600,
  fontSize: '14px',
  marginBottom: '8px',
  border: `1px solid ${COLORS.primary}`,
  cursor: busy ? 'wait' : 'pointer',
  opacity: busy ? 0.7 : 1,
})

function MeasurementsList({ measurements }) {
  const rows = [
    { label: 'Surface Area', value: `${measurements.surface_area_cm2} cm²` },
    { label: 'Volume', value: `${measurements.volume_cm3} cm³` },
    { label: 'Max Depth', value: `${measurements.max_depth_mm} mm` },
    { label: 'Width', value: `${measurements.width_cm} cm` },
    { label: 'Height', value: `${measurements.height_cm} cm` },
  ]
  const calibrated = measurements.scale_calibrated
  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <p style={{ fontSize: '11px', fontWeight: 700, color: COLORS.primary, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.75rem' }}>
        Measurements
      </p>
      {rows.map(row => (
        <div key={row.label} style={{
          display: 'flex', justifyContent: 'space-between',
          padding: '8px 0', borderBottom: '1px solid #f3f4f6', fontSize: '13px',
        }}>
          <span style={{ color: COLORS.textMuted }}>{row.label}</span>
          <span style={{ fontWeight: 600 }}>{row.value}</span>
        </div>
      ))}
      <p style={{
        marginTop: '0.6rem', fontSize: '12px', borderRadius: '6px', padding: '6px 10px',
        background: calibrated ? '#f0fdf4' : '#fffbeb',
        color: calibrated ? '#166534' : '#92400e',
        border: `1px solid ${calibrated ? '#bbf7d0' : '#fde68a'}`,
      }}>
        {calibrated
          ? 'Scale calibrated from the size reference in the video'
          : 'Uncalibrated scale — sizes are approximate. Include a bank card or coin next to the wound when filming.'}
      </p>
    </div>
  )
}

function ReconstructionQuality({ measurements }) {
  const hasFrameCounts =
    measurements.frames_registered != null && measurements.frames_extracted != null
  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <p style={{ fontSize: '11px', fontWeight: 700, color: COLORS.primary, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.75rem' }}>
        Reconstruction Quality
      </p>
      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
        <p style={{ fontSize: '28px', fontWeight: 700, color: COLORS.primary }}>
          {measurements.registration_rate != null ? `${measurements.registration_rate}%` : 'N/A'}
        </p>
        <p style={{ fontSize: '12px', color: COLORS.textMuted }}>
          {hasFrameCounts
            ? `${measurements.frames_registered} of ${measurements.frames_extracted} frames used`
            : 'Frame registration rate'}
        </p>
      </div>
    </div>
  )
}

// Right-hand sidebar: measurements, quality, view-mode toggles, and downloads.
export default function ViewerSidebar({
  scanId,
  measurements,
  depthMapCount,
  showDepth,
  onToggleDepth,
  splatView,
  splatLoading,
  onToggleSplat,
  smoothSurface,
  meshLoading,
  onToggleSmooth,
  fullScene,
  fullLoading,
  onToggleFullScene,
}) {
  return (
    <div style={{
      width: '280px', background: 'white', borderLeft: `1px solid ${COLORS.border}`,
      padding: '1.5rem', overflowY: 'auto',
    }}>
      <h2 style={{ fontWeight: 700, fontSize: '16px', marginBottom: '0.5rem' }}>3D Wound View</h2>
      <p style={{ color: COLORS.textMuted, fontSize: '13px', marginBottom: '1.5rem' }}>
        Scan ID: {scanId?.slice(0, 8)}...
      </p>

      {measurements && (
        <>
          <MeasurementsList measurements={measurements} />
          <ReconstructionQuality measurements={measurements} />
        </>
      )}

      <button
        onClick={onToggleSplat}
        disabled={splatLoading}
        style={toggleButtonStyle(splatView, splatLoading)}
      >
        {splatLoading ? 'Loading splats…' : (splatView ? 'Show Points' : 'Gaussian Splat View')}
      </button>

      <button
        onClick={onToggleSmooth}
        disabled={meshLoading}
        style={toggleButtonStyle(smoothSurface, meshLoading)}
      >
        {meshLoading ? 'Generating surface…' : (smoothSurface ? 'Show Points' : 'Smooth Surface')}
      </button>

      <button
        onClick={onToggleFullScene}
        disabled={fullLoading}
        style={toggleButtonStyle(fullScene, fullLoading)}
      >
        {fullLoading ? 'Loading full scene…' : (fullScene ? 'Show Wound Only' : 'Show Full Scene')}
      </button>

      {depthMapCount > 0 && (
        <button onClick={onToggleDepth} style={toggleButtonStyle(showDepth, false)}>
          {showDepth ? 'Hide' : 'Show'} AI Depth Maps ({depthMapCount})
        </button>
      )}

      <a
        href={scanUrls.reportPdf(scanId)}
        style={{
          display: 'block', background: COLORS.primary, color: 'white',
          padding: '10px', borderRadius: '8px', textAlign: 'center',
          textDecoration: 'none', fontWeight: 600, fontSize: '14px',
          marginBottom: '8px',
        }}
      >
        Download Report PDF
      </a>
      <a
        href="/patient"
        style={{
          display: 'block', background: 'white', color: '#374151',
          padding: '10px', borderRadius: '8px', textAlign: 'center',
          textDecoration: 'none', fontWeight: 500, fontSize: '14px',
          border: `1px solid ${COLORS.border}`,
        }}
      >
        Back to Portal
      </a>
    </div>
  )
}
