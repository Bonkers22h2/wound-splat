'use client'
import { controlButtonStyle, overlayLabelStyle } from './viewerStyles'

const AXES = ['x', 'y', 'z']

// Overlay panel with 90-degree rotation buttons for each axis plus a reset.
export default function OrientationControls({ onRotate, onReset }) {
  return (
    <div style={{
      position: 'absolute', top: '16px', left: '16px',
      background: 'rgba(0,0,0,0.6)', borderRadius: '10px', padding: '10px',
      display: 'flex', flexDirection: 'column', gap: '6px',
    }}>
      <p style={{ ...overlayLabelStyle, marginBottom: '2px' }}>ORIENTATION</p>
      {AXES.map(axis => (
        <div key={axis} style={{ display: 'flex', gap: '6px' }}>
          <button style={controlButtonStyle} onClick={() => onRotate(axis, -90)}>
            {axis.toUpperCase()} -90°
          </button>
          <button style={controlButtonStyle} onClick={() => onRotate(axis, 90)}>
            {axis.toUpperCase()} +90°
          </button>
        </div>
      ))}
      <button
        style={{ ...controlButtonStyle, marginTop: '4px', textAlign: 'center' }}
        onClick={onReset}
      >
        Reset
      </button>
    </div>
  )
}
