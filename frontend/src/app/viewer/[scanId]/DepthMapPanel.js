'use client'
import { scanUrls } from '@/lib/api'
import { controlButtonStyle, overlayLabelStyle } from './viewerStyles'

// Overlay panel for stepping through the AI-generated depth-map frames.
export default function DepthMapPanel({ scanId, depthMaps, depthIndex, onIndexChange, onClose }) {
  return (
    <div style={{
      position: 'absolute', top: '16px', right: '16px', width: '320px',
      background: 'rgba(0,0,0,0.82)', borderRadius: '10px', padding: '12px',
      display: 'flex', flexDirection: 'column', gap: '8px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={overlayLabelStyle}>AI DEPTH MAP</span>
        <button style={{ ...controlButtonStyle, padding: '2px 8px' }} onClick={onClose}>✕</button>
      </div>
      <img
        src={scanUrls.depthImage(scanId, depthMaps[depthIndex])}
        alt={`depth frame ${depthIndex + 1}`}
        style={{ width: '100%', borderRadius: '6px', display: 'block', background: '#111' }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          style={controlButtonStyle}
          onClick={() => onIndexChange(Math.max(0, depthIndex - 1))}
        >
          ◀
        </button>
        <input
          type="range" min={0} max={depthMaps.length - 1} value={depthIndex}
          onChange={e => onIndexChange(Number(e.target.value))}
          style={{ flex: 1 }}
        />
        <button
          style={controlButtonStyle}
          onClick={() => onIndexChange(Math.min(depthMaps.length - 1, depthIndex + 1))}
        >
          ▶
        </button>
      </div>
      <div style={{ textAlign: 'center', fontSize: '11px', color: '#9ca3af' }}>
        Frame {depthIndex + 1} / {depthMaps.length} ·{' '}
        <span style={{ color: '#ef4444' }}>near</span> → <span style={{ color: '#3b82f6' }}>far</span>
      </div>
    </div>
  )
}
