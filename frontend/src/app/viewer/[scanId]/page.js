'use client'
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import Navbar from '../../components/Navbar'

export default function ViewerPage() {
  const { scanId } = useParams()
  const mountRef = useRef(null)
  const pointsRef = useRef(null)
  const cameraRef = useRef(null)
  const controlsRef = useRef(null)
  const pointsObjRef = useRef(null)
  const meshRef = useRef(null)
  const centerRef = useRef(null)
  const scaleRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [measurements, setMeasurements] = useState(null)
  const [depthMaps, setDepthMaps] = useState([])
  const [depthIndex, setDepthIndex] = useState(0)
  const [showDepth, setShowDepth] = useState(false)
  const [smoothSurface, setSmoothSurface] = useState(false)
  const [meshLoading, setMeshLoading] = useState(false)

  useEffect(() => {
    loadMeasurements()
    loadDepthMaps()
    initViewer()
  }, [])

  const loadMeasurements = async () => {
    try {
      const res = await fetch(`/api/scans/${scanId}/measurements`)
      const data = await res.json()
      setMeasurements(data)
    } catch {}
  }

  const loadDepthMaps = async () => {
    try {
      const res = await fetch(`/api/scans/${scanId}/depths`)
      const data = await res.json()
      setDepthMaps(data.depths || [])
    } catch {}
  }

  // Lazily build the smooth mesh surface (Poisson, generated server-side) and
  // add it to the same group as the points so rotation/scale stay in sync.
  const loadMesh = async () => {
    const group = pointsRef.current
    if (!group) return
    setMeshLoading(true)
    const THREE = await import('three')
    const { PLYLoader } = await import('three/examples/jsm/loaders/PLYLoader.js')
    new PLYLoader().load(
      `/api/scans/${scanId}/mesh`,
      (geometry) => {
        geometry.computeVertexNormals()
        if (centerRef.current) {
          const c = centerRef.current
          geometry.translate(-c.x, -c.y, -c.z)
        }
        const hasColor = geometry.hasAttribute('color')
        const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
          vertexColors: hasColor,
          color: hasColor ? 0xffffff : 0xcf8e7d,
          roughness: 0.9, metalness: 0.0,
          side: THREE.DoubleSide
        }))
        if (scaleRef.current) mesh.scale.setScalar(scaleRef.current)
        meshRef.current = mesh
        group.add(mesh)
        if (pointsObjRef.current) pointsObjRef.current.visible = false
        setMeshLoading(false)
      },
      undefined,
      (err) => {
        console.error('mesh load error:', err)
        setMeshLoading(false)
        setSmoothSurface(false)
      }
    )
  }

  const toggleSmooth = async () => {
    const next = !smoothSurface
    setSmoothSurface(next)
    if (next) {
      if (meshRef.current) {
        meshRef.current.visible = true
        if (pointsObjRef.current) pointsObjRef.current.visible = false
      } else {
        await loadMesh()
      }
    } else {
      if (meshRef.current) meshRef.current.visible = false
      if (pointsObjRef.current) pointsObjRef.current.visible = true
    }
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
    if (points) points.rotation.set(0, 0, 0)
    // Also bring the camera back to the default framing of the wound
    const camera = cameraRef.current
    const controls = controlsRef.current
    if (camera && controls) {
      camera.position.set(0, 0, 22)
      controls.target.set(0, 0, 0)
      controls.update()
    }
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
    cameraRef.current = camera
    controlsRef.current = controls

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
            size: 0.25,
            vertexColors: true,
            sizeAttenuation: true
          })
        } else {
          material = new THREE.PointsMaterial({
            size: 0.25,
            color: 0x1D9E75,
            sizeAttenuation: true
          })
        }

        const points = new THREE.Points(geometry, material)

        // Recenter the ACTUAL vertices on the origin (translate the geometry,
        // not the object) so the wound sits exactly at the orbit pivot.
        geometry.computeBoundingBox()
        const box = geometry.boundingBox
        const center = new THREE.Vector3()
        box.getCenter(center)
        geometry.translate(-center.x, -center.y, -center.z)

        // Normalize size so the wound fills the view regardless of scan scale.
        // Scaling now happens around the origin, so the wound stays centered.
        const size = new THREE.Vector3()
        box.getSize(size)
        const maxDim = Math.max(size.x, size.y, size.z) || 1
        const scale = 14 / maxDim
        points.scale.setScalar(scale)

        // Wrap in a group so the orientation buttons rotate around the centre
        const group = new THREE.Group()
        group.add(points)
        scene.add(group)
        pointsRef.current = group
        pointsObjRef.current = points
        centerRef.current = center.clone()
        scaleRef.current = scale

        // Aim the camera AND the orbit pivot at the wound centre (origin),
        // so dragging spins the wound in place instead of swinging it around.
        controls.target.set(0, 0, 0)
        controls.minDistance = 5
        controls.maxDistance = 60
        controls.rotateSpeed = 0.9
        camera.position.set(0, 0, 22)
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

          {/* AI Depth map viewer */}
          {!loading && !error && showDepth && depthMaps.length > 0 && (
            <div style={{
              position: 'absolute', top: '16px', right: '16px', width: '320px',
              background: 'rgba(0,0,0,0.82)', borderRadius: '10px', padding: '12px',
              display: 'flex', flexDirection: 'column', gap: '8px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: '#9ca3af', fontWeight: 600 }}>AI DEPTH MAP</span>
                <button style={{ ...rotateBtnStyle, padding: '2px 8px' }} onClick={() => setShowDepth(false)}>✕</button>
              </div>
              <img
                src={`/api/scans/${scanId}/depth/${depthMaps[depthIndex]}`}
                alt={`depth frame ${depthIndex + 1}`}
                style={{ width: '100%', borderRadius: '6px', display: 'block', background: '#111' }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button style={rotateBtnStyle} onClick={() => setDepthIndex(i => Math.max(0, i - 1))}>◀</button>
                <input
                  type="range" min={0} max={depthMaps.length - 1} value={depthIndex}
                  onChange={e => setDepthIndex(Number(e.target.value))}
                  style={{ flex: 1 }}
                />
                <button style={rotateBtnStyle} onClick={() => setDepthIndex(i => Math.min(depthMaps.length - 1, i + 1))}>▶</button>
              </div>
              <div style={{ textAlign: 'center', fontSize: '11px', color: '#9ca3af' }}>
                Frame {depthIndex + 1} / {depthMaps.length} · <span style={{ color: '#ef4444' }}>near</span> → <span style={{ color: '#3b82f6' }}>far</span>
              </div>
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

          <button
            onClick={toggleSmooth}
            disabled={meshLoading}
            style={{
              display: 'block', width: '100%', background: smoothSurface ? '#0F6E56' : 'white',
              color: smoothSurface ? 'white' : '#0F6E56', padding: '10px', borderRadius: '8px',
              textAlign: 'center', fontWeight: 600, fontSize: '14px', marginBottom: '8px',
              border: '1px solid #0F6E56', cursor: meshLoading ? 'wait' : 'pointer', opacity: meshLoading ? 0.7 : 1
            }}
          >
            {meshLoading ? 'Generating surface…' : (smoothSurface ? 'Show Points' : 'Smooth Surface')}
          </button>

          {depthMaps.length > 0 && (
            <button
              onClick={() => setShowDepth(s => !s)}
              style={{
                display: 'block', width: '100%', background: showDepth ? '#0F6E56' : 'white',
                color: showDepth ? 'white' : '#0F6E56', padding: '10px', borderRadius: '8px',
                textAlign: 'center', fontWeight: 600, fontSize: '14px', marginBottom: '8px',
                border: '1px solid #0F6E56', cursor: 'pointer'
              }}
            >
              {showDepth ? 'Hide' : 'Show'} AI Depth Maps ({depthMaps.length})
            </button>
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