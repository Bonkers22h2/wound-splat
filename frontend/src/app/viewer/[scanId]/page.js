'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Image from 'next/image'
import Navbar from '../../components/Navbar'
import { scanApi } from '@/lib/api'
import useWoundViewer from './useWoundViewer'
import OrientationControls from './OrientationControls'
import ViewerSidebar from './ViewerSidebar'
import { DEMO_MEASUREMENTS } from '@/lib/demo'

export default function ViewerPage() {
  const { scanId } = useParams()
  const viewer = useWoundViewer(scanId)

  const [measurements, setMeasurements] = useState(null)

  useEffect(() => {
    if (String(scanId).startsWith('demo-')) {
      setMeasurements(DEMO_MEASUREMENTS)
      return
    }
    scanApi.measurements(scanId).then(setMeasurements).catch(() => {})
  }, [scanId])

  const viewerReady = !viewer.loading && !viewer.error

  return (
    <>
      <Navbar />
      <div className="viewer-shell">
        <div className="viewer-canvas">
          <div ref={viewer.mountRef} style={{ width: '100%', height: '100%' }} />
          {String(scanId).startsWith('demo-') && (
            <div style={{ position:'absolute', inset:0, display:'grid', placeItems:'center', pointerEvents:'none' }}>
              <div style={{ width:'min(44vw,380px)', aspectRatio:'1', borderRadius:'50%', background:'radial-gradient(circle at 48% 48%,#10B981 0 18%,#F59E0B 19% 40%,#3B82F6 41% 47%,rgba(16,185,129,.20) 48% 67%,rgba(59,130,246,.12) 68% 76%,transparent 77%)', boxShadow:'0 26px 80px rgba(16,185,129,.20), inset 0 0 30px rgba(255,255,255,.10)', transform:'perspective(600px) rotateX(8deg)' }}>
                <div style={{ position:'relative', width:'100%', height:'100%', borderRadius:'50%', border:'1px solid rgba(226,232,240,.12)' }} />
              </div>
            </div>
          )}

          {viewer.loading && (
            <div className="viewer-loading">
              <div className="brand-mark" style={{ marginBottom:'12px' }}><Image src="/wound-splat-logo.png" alt="" fill sizes="38px" /></div>
              <p style={{ fontWeight:750 }}>Loading 3D wound model</p>
              <p style={{ fontSize:'12px', color:'#94A3B8', marginTop:'6px' }}>Preparing the reconstruction</p>
            </div>
          )}

          {viewer.error && (
            <div className="viewer-loading">
              <div className="status status-failed" style={{ marginBottom:'10px' }}>Model unavailable</div>
              <p style={{ fontWeight:750 }}>{viewer.error}</p>
            </div>
          )}

          {viewerReady && (
            <div className="viewer-controls">
              <OrientationControls onRotate={viewer.rotateModel} onReset={viewer.resetRotation} />
            </div>
          )}

          {viewerReady && (
            <div className="viewer-hint">Drag to rotate · Scroll to zoom · Right-click to pan</div>
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
