'use client'
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import Navbar from '../../components/Navbar'

export default function ViewerPage() {
  const { scanId } = useParams()
  const mountRef = useRef(null)
  const pointsRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [measurements, setMeasurements] = useState(null)

  useEffect(() => {
    loadMeasurements()
    initViewer()
  }, [])

  const loadMeasurements = async () => {
    try {
      const res = await fetch(`/api/scans/${scanId}/measurements`)
      const data = await res.json()
      setMeasurements(data)
    } catch {}
  }

  const rotateModel = (axis, degrees) => {
    const points = pointsRef.current
    if (!points) return
    const rad = (degrees * Math.PI) / 180
    if (axis === 'x') points.rotation.x += rad
    if (axis === 'y') points.rotation.y += rad
    if (axis === 'z') points.rotation.z += rad
  }

  const resetRotation = () => {
    const points = pointsRef.current
    if (!points) return
    points.rotation.set(0, 0, 0)
  }

  const initViewer = async () => {
    // Dynamically import three.js
    const THREE = await import('three')
    const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js')
    const { PLYLoader } = await import('three/examples/jsm/loaders/PLYLoader.js')

    const container = mountRef.current
    if (!container) return

    // Scene setup
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0a0f0d)

    const camera = new THREE.PerspectiveCamera(
      60, container.clientWidth / container.clientHeight, 0.01, 1000
    )
    camera.position.set(0, 0, 30)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(container.clientWidth, container.clientHeight)
    renderer.setPixelRatio(window.devicePixelRatio)
    container.appendChild(renderer.domElement)

    // Controls - free rotate, zoom, pan (no auto-rotation)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05

    // Lighting
    const ambient = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambient)
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8)
    dirLight.position.set(10, 10, 10)
    scene.add(dirLight)

    // Grid
    const grid = new THREE.GridHelper(40, 20, 0x1D9E75, 0x0F6E56)
    grid.position.y = -10
    scene.add(grid)

    // Load PLY
    const loader = new PLYLoader()
    loader.load(
      `/api/scans/${scanId}/ply`,
      (geometry) => {
        geometry.computeVertexNormals()

        // Check if geometry has colors
        let material
        if (geometry.hasAttribute('color')) {
          material = new THREE.PointsMaterial({
            size: 0.15,
            vertexColors: true,
            sizeAttenuation: true
          })
        } else {
          material = new THREE.PointsMaterial({
            size: 0.15,
            color: 0x1D9E75,
            sizeAttenuation: true
          })
        }

        const points = new THREE.Points(geometry, material)

        // Center the geometry
        geometry.computeBoundingBox()
        const box = geometry.boundingBox
        const center = new THREE.Vector3()
        box.getCenter(center)
        points.position.sub(center)

        // Scale to fit view
        const size = new THREE.Vector3()
        box.getSize(size)
        const maxDim = Math.max(size.x, size.y, size.z)
        const scale = 20 / maxDim
        points.scale.setScalar(scale)

        // Wrap in a group so position offset + rotation don't conflict
        const group = new THREE.Group()
        group.add(points)
        scene.add(group)
        pointsRef.current = group

        camera.position.set(0, 0, 25)
        controls.update()
        setLoading(false)
      },
      (progress) => {
        console.log('Loading:', (progress.loaded / progress.total * 100).toFixed(0) + '%')
      },
      (err) => {
        console.error('PLY load error:', err)
        setError('Could not load 3D model. The scan may still be processing.')
        setLoading(false)
      }
    )

    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    // Handle resize
    const handleResize = () => {
      if (!container) return
      camera.aspect = container.clientWidth / container.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(container.clientWidth, container.clientHeight)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      renderer.dispose()
    }
  }

  const rotateBtnStyle = {
    padding: '6px 10px',
    fontSize: '12px',
    borderRadius: '6px',
    border: '1px solid rgba(255,255,255,0.2)',
    background: 'rgba(255,255,255,0.08)',
    color: '#e5e7eb',
    cursor: 'pointer',
    fontWeight: 500
  }

  return (
    <>
      <Navbar />
      <div style={{ display: 'flex', height: 'calc(100vh - 56px)' }}>

        {/* 3D Viewer */}
        <div style={{ flex: 1, position: 'relative', background: '#0a0f0d' }}>
          <div ref={mountRef} style={{ width: '100%', height: '100%' }} />

          {loading && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(10,15,13,0.8)', color: '#1D9E75', flexDirection: 'column', gap: '12px'
            }}>
              <div style={{ fontSize: '32px' }}>⚕</div>
              <p style={{ fontWeight: 600 }}>Loading 3D wound model...</p>
              <p style={{ fontSize: '13px', color: '#6b7280' }}>This may take a moment</p>
            </div>
          )}

          {error && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(10,15,13,0.9)', color: 'white', flexDirection: 'column', gap: '12px'
            }}>
              <div style={{ fontSize: '32px' }}>⚠️</div>
              <p style={{ fontWeight: 600 }}>{error}</p>
            </div>
          )}

          {/* Rotation controls */}
          {!loading && !error && (
            <div style={{
              position: 'absolute', top: '16px', left: '16px',
              background: 'rgba(0,0,0,0.6)', borderRadius: '10px', padding: '10px',
              display: 'flex', flexDirection: 'column', gap: '6px'
            }}>
              <p style={{ fontSize: '11px', color: '#9ca3af', marginBottom: '2px', fontWeight: 600 }}>
                ORIENTATION
              </p>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button style={rotateBtnStyle} onClick={() => rotateModel('x', -90)}>X -90°</button>
                <button style={rotateBtnStyle} onClick={() => rotateModel('x', 90)}>X +90°</button>
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button style={rotateBtnStyle} onClick={() => rotateModel('y', -90)}>Y -90°</button>
                <button style={rotateBtnStyle} onClick={() => rotateModel('y', 90)}>Y +90°</button>
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button style={rotateBtnStyle} onClick={() => rotateModel('z', -90)}>Z -90°</button>
                <button style={rotateBtnStyle} onClick={() => rotateModel('z', 90)}>Z +90°</button>
              </div>
              <button style={{ ...rotateBtnStyle, marginTop: '4px', textAlign: 'center' }} onClick={resetRotation}>
                Reset
              </button>
            </div>
          )}

          {/* Controls hint */}
          {!loading && !error && (
            <div style={{
              position: 'absolute', bottom: '16px', left: '50%', transform: 'translateX(-50%)',
              background: 'rgba(0,0,0,0.6)', color: '#9ca3af', padding: '6px 16px',
              borderRadius: '999px', fontSize: '12px'
            }}>
              🖱️ Drag to rotate · Scroll to zoom · Right-click to pan
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div style={{
          width: '280px', background: 'white', borderLeft: '1px solid #e5e7eb',
          padding: '1.5rem', overflowY: 'auto'
        }}>
          <h2 style={{ fontWeight: 700, fontSize: '16px', marginBottom: '0.5rem' }}>3D Wound View</h2>
          <p style={{ color: '#6b7280', fontSize: '13px', marginBottom: '1.5rem' }}>
            Scan ID: {scanId?.slice(0, 8)}...
          </p>

          {measurements && (
            <>
              <div style={{ marginBottom: '1.5rem' }}>
                <p style={{ fontSize: '11px', fontWeight: 700, color: '#0F6E56', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.75rem' }}>
                  Measurements
                </p>
                {[
                  { label: 'Surface Area', value: `${measurements.surface_area_cm2} cm²` },
                  { label: 'Volume', value: `${measurements.volume_cm3} cm³` },
                  { label: 'Max Depth', value: `${measurements.max_depth_mm} mm` },
                  { label: 'Width', value: `${measurements.width_cm} cm` },
                  { label: 'Height', value: `${measurements.height_cm} cm` },
                ].map((m, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between',
                    padding: '8px 0', borderBottom: '1px solid #f3f4f6', fontSize: '13px'
                  }}>
                    <span style={{ color: '#6b7280' }}>{m.label}</span>
                    <span style={{ fontWeight: 600 }}>{m.value}</span>
                  </div>
                ))}
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <p style={{ fontSize: '11px', fontWeight: 700, color: '#0F6E56', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.75rem' }}>
                  Reconstruction Quality
                </p>
                <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                  <p style={{ fontSize: '28px', fontWeight: 700, color: '#0F6E56' }}>
                    {measurements.registration_rate != null ? `${measurements.registration_rate}%` : 'N/A'}
                  </p>
                  <p style={{ fontSize: '12px', color: '#6b7280' }}>
                    {measurements.frames_registered != null && measurements.frames_extracted != null
                      ? `${measurements.frames_registered} of ${measurements.frames_extracted} frames used`
                      : 'Frame registration rate'}
                  </p>
                </div>
              </div>
            </>
          )}

          <a
            href={`/api/reports/${scanId}/pdf`}
            style={{
              display: 'block', background: '#0F6E56', color: 'white',
              padding: '10px', borderRadius: '8px', textAlign: 'center',
              textDecoration: 'none', fontWeight: 600, fontSize: '14px',
              marginBottom: '8px'
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
              border: '1px solid #e5e7eb'
            }}
          >
            Back to Portal
          </a>
        </div>
      </div>
    </>
  )
}