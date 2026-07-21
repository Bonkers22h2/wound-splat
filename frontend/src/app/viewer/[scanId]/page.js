'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Navbar from '../../components/Navbar'
import { scanApi } from '@/lib/api'
import useWoundViewer from './useWoundViewer'
import OrientationControls from './OrientationControls'
import ViewerSidebar from './ViewerSidebar'

const VIEWER_BACKGROUND = '#0a0f0d'

export default function ViewerPage() {
  const { scanId } = useParams()
  const viewer = useWoundViewer(scanId)

  const [measurements, setMeasurements] = useState(null)

  useEffect(() => {
    scanApi.measurements(scanId).then(setMeasurements).catch(() => {})
  }, [scanId])

  const viewerReady = !viewer.loading && !viewer.error

  return (
    <>
      <Navbar />
      <div style={{ display: 'flex', height: 'calc(100vh - 56px)' }}>

        {/* 3D viewer canvas + overlays */}
        <div style={{ flex: 1, position: 'relative', background: VIEWER_BACKGROUND }}>
          <div ref={viewer.mountRef} style={{ width: '100%', height: '100%' }} />

          {viewer.loading && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(10,15,13,0.8)', color: '#1D9E75', flexDirection: 'column', gap: '12px',
            }}>
              <div style={{ fontSize: '32px' }}>⚕</div>
              <p style={{ fontWeight: 600 }}>Loading 3D wound model...</p>
              <p style={{ fontSize: '13px', color: '#6b7280' }}>This may take a moment</p>
            </div>
          )}

          {viewer.error && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(10,15,13,0.9)', color: 'white', flexDirection: 'column', gap: '12px',
            }}>
              <div style={{ fontSize: '32px' }}>⚠️</div>
              <p style={{ fontWeight: 600 }}>{viewer.error}</p>
            </div>
          )}

          {viewerReady && (
            <OrientationControls onRotate={viewer.rotateModel} onReset={viewer.resetRotation} />
          )}

          {viewerReady && (
            <div style={{
              position: 'absolute', bottom: '16px', left: '50%', transform: 'translateX(-50%)',
              background: 'rgba(0,0,0,0.6)', color: '#9ca3af', padding: '6px 16px',
              borderRadius: '999px', fontSize: '12px',
            }}>
              🖱️ Drag to rotate · Scroll to zoom · Right-click to pan
            </div>
          )}

        </div>

        <ViewerSidebar
          scanId={scanId}
          measurements={measurements}
          splatView={viewer.splatView}
          splatLoading={viewer.splatLoading}
          onToggleSplat={viewer.toggleSplat}
          smoothSurface={viewer.smoothSurface}
          meshLoading={viewer.meshLoading}
          onToggleSmooth={viewer.toggleSmooth}
          fullScene={viewer.fullScene}
          fullLoading={viewer.fullLoading}
          onToggleFullScene={viewer.toggleFullScene}
        />
      </div>
    </>
  )
}
