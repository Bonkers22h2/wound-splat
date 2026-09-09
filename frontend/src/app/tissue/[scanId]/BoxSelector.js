'use client'
import { useRef, useState } from 'react'
import { COLORS } from '@/lib/theme'

// The image is displayed scaled to fit, but the backend needs coordinates in
// the original photo's pixels. Everything below is tracked in display pixels
// and converted once, on release.
function toNaturalBox(box, img) {
  const scaleX = img.naturalWidth / img.clientWidth
  const scaleY = img.naturalHeight / img.clientHeight
  return {
    left: Math.round(Math.min(box.x1, box.x2) * scaleX),
    top: Math.round(Math.min(box.y1, box.y2) * scaleY),
    right: Math.round(Math.max(box.x1, box.x2) * scaleX),
    bottom: Math.round(Math.max(box.y1, box.y2) * scaleY),
  }
}

export default function BoxSelector({ src, onChange, disabled }) {
  const imgRef = useRef(null)
  const [box, setBox] = useState(null)
  const [drawing, setDrawing] = useState(false)

  const pointAt = (event) => {
    const rect = imgRef.current.getBoundingClientRect()
    return {
      x: Math.max(0, Math.min(event.clientX - rect.left, rect.width)),
      y: Math.max(0, Math.min(event.clientY - rect.top, rect.height)),
    }
  }

  const start = (event) => {
    if (disabled) return
    event.preventDefault()
    const { x, y } = pointAt(event)
    setBox({ x1: x, y1: y, x2: x, y2: y })
    setDrawing(true)
    onChange(null)
  }

  const move = (event) => {
    if (!drawing) return
    const { x, y } = pointAt(event)
    setBox((previous) => ({ ...previous, x2: x, y2: y }))
  }

  const finish = () => {
    if (!drawing) return
    setDrawing(false)
    const width = Math.abs(box.x2 - box.x1)
    const height = Math.abs(box.y2 - box.y1)
    // A stray click is not a box. Below a few pixels, treat it as a reset
    // rather than sending a sliver the model cannot use.
    if (width < 8 || height < 8) {
      setBox(null)
      onChange(null)
      return
    }
    onChange(toNaturalBox(box, imgRef.current))
  }

  const rect = box && {
    left: Math.min(box.x1, box.x2),
    top: Math.min(box.y1, box.y2),
    width: Math.abs(box.x2 - box.x1),
    height: Math.abs(box.y2 - box.y1),
  }

  return (
    <div
      style={{ position: 'relative', display: 'inline-block', lineHeight: 0 }}
      onMouseMove={move}
      onMouseUp={finish}
      onMouseLeave={finish}
    >
      <img
        ref={imgRef}
        src={src}
        alt="Opening frame from the scan, for selecting the wound"
        onMouseDown={start}
        draggable={false}
        style={{
          maxHeight: '70vh', maxWidth: '100%', borderRadius: '8px',
          cursor: disabled ? 'wait' : 'crosshair', userSelect: 'none',
        }}
      />
      {rect && (
        <div style={{
          position: 'absolute', ...rect,
          border: `2px solid ${COLORS.primaryLight}`,
          background: 'rgba(29,158,117,0.15)',
          pointerEvents: 'none', borderRadius: '2px',
        }} />
      )}
    </div>
  )
}
