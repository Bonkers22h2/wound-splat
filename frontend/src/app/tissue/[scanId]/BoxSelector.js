'use client'
import { useEffect, useRef, useState } from 'react'
import { drawBox, moveBox, resizeBox } from './selection.mjs'
import styles from './selection.module.css'

const corners = { nw: 'Top left', ne: 'Top right', sw: 'Bottom left', se: 'Bottom right' }

export default function BoxSelector({ src, box, onChange, disabled, onInteraction }) {
  const image = useRef(null)
  const preview = useRef(null)
  const gesture = useRef(null)
  const [size, setSize] = useState(null)
  const [failed, setFailed] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!box || !size || !preview.current) return
    const canvas = preview.current
    const width = box.right - box.left
    const height = box.bottom - box.top
    canvas.width = Math.min(720, width)
    canvas.height = Math.max(1, Math.round(canvas.width * height / width))
    canvas.getContext('2d').drawImage(image.current, box.left, box.top, width, height, 0, 0, canvas.width, canvas.height)
  }, [box, size])

  const pointAt = (event) => {
    const rect = image.current.getBoundingClientRect()
    return {
      x: Math.round(Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)) * size.width),
      y: Math.round(Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) * size.height),
    }
  }
  const start = (event, mode) => {
    if (disabled || !size || gesture.current || event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    gesture.current = { mode, start: pointAt(event), original: box, pointer: event.pointerId }
    onInteraction(true)
    setNotice('')
  }
  const update = (event) => {
    const active = gesture.current
    if (!active || active.pointer !== event.pointerId) return
    const point = pointAt(event)
    const next = active.mode === 'draw' ? drawBox(active.start, point)
      : active.mode === 'move' ? moveBox(active.original, point.x - active.start.x, point.y - active.start.y, size)
        : resizeBox(active.original, active.mode, point, size)
    active.latest = next
    if (next.right - next.left >= 8 && next.bottom - next.top >= 8) onChange(next)
  }
  const finish = (event, cancel = false) => {
    const active = gesture.current
    if (!active || active.pointer !== event.pointerId) return
    if (!cancel) update(event)
    const next = active.latest
    if (cancel) onChange(active.original)
    else if (!next || next.right - next.left < 8 || next.bottom - next.top < 8) {
      onChange(active.original)
      setNotice('That selection was too small. Drag a larger box around the wound.')
    }
    gesture.current = null
    onInteraction(false)
  }
  const keyboard = (event, corner) => {
    if (disabled || !box || !size || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
    event.preventDefault()
    const step = event.shiftKey ? 10 : 1
    const dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0
    const dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0
    onChange(corner ? resizeBox(box, corner, {
      x: (corner.includes('w') ? box.left : box.right) + dx,
      y: (corner.includes('n') ? box.top : box.bottom) + dy,
    }, size) : moveBox(box, dx, dy, size))
  }
  const rect = box && size ? {
    left: `${box.left / size.width * 100}%`, top: `${box.top / size.height * 100}%`,
    width: `${(box.right - box.left) / size.width * 100}%`, height: `${(box.bottom - box.top) / size.height * 100}%`,
  } : null

  return (
    <section className={styles.selector}>
      <h2>1. Select the wound</h2>
      <p id="selection-help">Drag on the photo to draw. Move the box or drag its corners to adjust it.</p>
      {!size && !failed && <p role="status">Loading wound photo…</p>}
      {failed && <p role="alert">The wound photo could not load. Return to the 3D model and check that the scan has finished, then reopen this page.</p>}
      <div className={styles.frame}
        onPointerDown={(event) => start(event, 'draw')}
        onPointerMove={update} onPointerUp={(event) => finish(event)}
        onPointerCancel={(event) => finish(event, true)}
        onLostPointerCapture={(event) => finish(event, true)}>
        <img ref={image} src={src} alt="Scan photo for selecting the wound" draggable={false}
          onLoad={(event) => { setSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight }); setFailed(false) }}
          onError={() => { setFailed(true); setSize(null); onChange(null) }} />
        {rect && <div className={styles.box} style={rect}>
          <button type="button" className={styles.move} aria-label="Move selection using arrow keys" aria-describedby="selection-help"
            disabled={disabled} onPointerDown={(event) => start(event, 'move')} onKeyDown={(event) => keyboard(event)} />
          {Object.entries(corners).map(([corner, label]) => <button key={corner} type="button"
            className={`${styles.handle} ${styles[corner]}`} aria-label={`${label} corner: use arrow keys to resize`}
            disabled={disabled} onPointerDown={(event) => start(event, corner)} onKeyDown={(event) => keyboard(event, corner)} />)}
        </div>}
      </div>
      <div className={styles.toolbar}>
        <button type="button" disabled={disabled || !box} onClick={() => { onChange(null); setNotice('Selection cleared.') }}>Reset selection</button>
        <button type="button" disabled={disabled || !size || !!box} onClick={() => onChange({
          left: Math.round(size.width * .25), top: Math.round(size.height * .25),
          right: Math.round(size.width * .75), bottom: Math.round(size.height * .75),
        })}>Start with a centered box</button>
      </div>
      <p className={styles.hint}>Keyboard: focus the box or a corner and use arrow keys. Hold Shift for larger steps.</p>
      <p role="status" className={styles.hint}>{notice}</p>
      <h2>2. Check the close-up</h2>
      <p>Include the wound and its relevant edge. Keep unrelated skin, the coin, and other background objects outside the box.</p>
      {box && size ? <canvas ref={preview} className={styles.preview} role="img" aria-label="Close-up of the exact area selected for tissue analysis" />
        : <div className={styles.empty}>Your selected area will appear here.</div>}
    </section>
  )
}
