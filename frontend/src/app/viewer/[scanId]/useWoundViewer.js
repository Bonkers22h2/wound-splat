'use client'
import { useEffect, useRef, useState } from 'react'
import { scanUrls } from '@/lib/api'

// Every scan is normalized to this world size so wounds fill the view the
// same way regardless of their real-world scale.
const NORMALIZED_MODEL_SIZE = 14
const DEFAULT_CAMERA_Z = 22

/**
 * Owns the three.js scene for a wound scan and the three view modes
 * (point cloud, smooth mesh, Gaussian splat). The point cloud loads on mount;
 * mesh and splat load lazily the first time they are toggled on. All views
 * share one rotation group so the orientation buttons affect them equally.
 */
export default function useWoundViewer(scanId) {
  const mountRef = useRef(null)
  const groupRef = useRef(null) // rotation group shared by all views
  const pointsRef = useRef(null) // raw point-cloud object
  const meshRef = useRef(null) // smooth Poisson mesh (lazy)
  const splatRef = useRef(null) // Gaussian-splat viewer (lazy)
  const cameraRef = useRef(null)
  const controlsRef = useRef(null)
  const centerRef = useRef(null) // original geometry center, reused to align the mesh
  const scaleRef = useRef(null) // normalization scale, reused to align the mesh

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [smoothSurface, setSmoothSurface] = useState(false)
  const [meshLoading, setMeshLoading] = useState(false)
  const [splatView, setSplatView] = useState(false)
  const [splatLoading, setSplatLoading] = useState(false)

  useEffect(() => {
    let disposed = false
    let renderer = null
    let animationFrame = null
    let handleResize = null

    const init = async () => {
      const THREE = await import('three')
      const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js')
      const { PLYLoader } = await import('three/examples/jsm/loaders/PLYLoader.js')

      const container = mountRef.current
      if (!container || disposed) return

      const scene = new THREE.Scene()
      scene.background = new THREE.Color(0x0a0f0d)

      const camera = new THREE.PerspectiveCamera(
        60, container.clientWidth / container.clientHeight, 0.01, 1000
      )
      camera.position.set(0, 0, 30)

      renderer = new THREE.WebGLRenderer({ antialias: true })
      renderer.setSize(container.clientWidth, container.clientHeight)
      renderer.setPixelRatio(window.devicePixelRatio)
      container.appendChild(renderer.domElement)

      // Free rotate, zoom, pan (no auto-rotation).
      const controls = new OrbitControls(camera, renderer.domElement)
      controls.enableDamping = true
      controls.dampingFactor = 0.05
      cameraRef.current = camera
      controlsRef.current = controls

      scene.add(new THREE.AmbientLight(0xffffff, 0.6))
      const dirLight = new THREE.DirectionalLight(0xffffff, 0.8)
      dirLight.position.set(10, 10, 10)
      scene.add(dirLight)

      const grid = new THREE.GridHelper(40, 20, 0x1D9E75, 0x0F6E56)
      grid.position.y = -10
      scene.add(grid)

      new PLYLoader().load(
        scanUrls.ply(scanId),
        (geometry) => {
          if (disposed) return
          geometry.computeVertexNormals()

          const material = new THREE.PointsMaterial({
            size: 0.25,
            sizeAttenuation: true,
            ...(geometry.hasAttribute('color')
              ? { vertexColors: true }
              : { color: 0x1D9E75 }),
          })
          const points = new THREE.Points(geometry, material)

          // Recenter the ACTUAL vertices on the origin (translate the geometry,
          // not the object) so the wound sits exactly at the orbit pivot.
          geometry.computeBoundingBox()
          const box = geometry.boundingBox
          const center = new THREE.Vector3()
          box.getCenter(center)
          geometry.translate(-center.x, -center.y, -center.z)

          // Normalize size so the wound fills the view regardless of scan scale.
          // Scaling happens around the origin, so the wound stays centered.
          const size = new THREE.Vector3()
          box.getSize(size)
          const maxDim = Math.max(size.x, size.y, size.z) || 1
          const scale = NORMALIZED_MODEL_SIZE / maxDim
          points.scale.setScalar(scale)

          // Wrap in a group so the orientation buttons rotate around the centre.
          const group = new THREE.Group()
          group.add(points)
          scene.add(group)
          groupRef.current = group
          pointsRef.current = points
          centerRef.current = center.clone()
          scaleRef.current = scale

          // Aim the camera AND the orbit pivot at the wound centre (origin),
          // so dragging spins the wound in place instead of swinging it around.
          controls.target.set(0, 0, 0)
          controls.minDistance = 5
          controls.maxDistance = 60
          controls.rotateSpeed = 0.9
          camera.position.set(0, 0, DEFAULT_CAMERA_Z)
          controls.update()
          setLoading(false)
        },
        undefined,
        (err) => {
          if (disposed) return
          console.error('PLY load error:', err)
          setError('Could not load 3D model. The scan may still be processing.')
          setLoading(false)
        }
      )

      const animate = () => {
        animationFrame = requestAnimationFrame(animate)
        controls.update()
        renderer.render(scene, camera)
      }
      animate()

      handleResize = () => {
        if (!container) return
        camera.aspect = container.clientWidth / container.clientHeight
        camera.updateProjectionMatrix()
        renderer.setSize(container.clientWidth, container.clientHeight)
      }
      window.addEventListener('resize', handleResize)
    }

    init()

    return () => {
      disposed = true
      if (animationFrame) cancelAnimationFrame(animationFrame)
      if (handleResize) window.removeEventListener('resize', handleResize)
      if (renderer) {
        renderer.dispose()
        renderer.domElement.remove()
      }
    }
  }, [scanId])

  // Lazily build the smooth mesh surface (Poisson, generated server-side) and
  // add it to the same group as the points so rotation/scale stay in sync.
  const loadMesh = async () => {
    const group = groupRef.current
    if (!group) return
    setMeshLoading(true)
    const THREE = await import('three')
    const { PLYLoader } = await import('three/examples/jsm/loaders/PLYLoader.js')
    new PLYLoader().load(
      scanUrls.mesh(scanId),
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
          roughness: 0.9,
          metalness: 0.0,
          side: THREE.DoubleSide,
        }))
        if (scaleRef.current) mesh.scale.setScalar(scaleRef.current)
        meshRef.current = mesh
        group.add(mesh)
        if (pointsRef.current) pointsRef.current.visible = false
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

  // Lazily build the real Gaussian-splat view. Unlike the points/mesh views
  // (which use the cropped wound_only.ply via /ply), this loads the full 3DGS
  // point_cloud.ply with its Gaussian fields intact from /splat, and renders it
  // with @mkkellogg/gaussian-splats-3d. The DropInViewer is a THREE.Object3D, so
  // it goes in the same rotation group and the orientation buttons still work.
  const loadSplat = async () => {
    const group = groupRef.current
    if (!group) return
    setSplatLoading(true)
    const THREE = await import('three')
    const GS = await import('@mkkellogg/gaussian-splats-3d')
    // sharedMemoryForWorkers:false avoids needing COOP/COEP cross-origin-isolation
    // headers; gpuAcceleratedSort follows suit. ~82k splats sort fine on the CPU.
    const dropIn = new GS.DropInViewer({
      gpuAcceleratedSort: false,
      sharedMemoryForWorkers: false,
      sphericalHarmonicsDegree: 0,
    })
    try {
      await dropIn.addSplatScene(scanUrls.splat(scanId), {
        // Our endpoint URL ends in /splat (not .ply), so the library can't sniff
        // the format from the extension — tell it explicitly this is a 3DGS .ply.
        format: GS.SceneFormat.Ply,
        splatAlphaRemovalThreshold: 5,
        showLoadingUI: false,
      })
      // Center + normalize to the same framing as the points view, using the
      // splat's own bounding box (the full scene has different bounds than the
      // cropped wound cloud).
      const bbox = dropIn.splatMesh.computeBoundingBox(false)
      const center = new THREE.Vector3()
      bbox.getCenter(center)
      const size = new THREE.Vector3()
      bbox.getSize(size)
      const maxDim = Math.max(size.x, size.y, size.z) || 1
      const scale = NORMALIZED_MODEL_SIZE / maxDim
      dropIn.scale.setScalar(scale)
      dropIn.position.set(-center.x * scale, -center.y * scale, -center.z * scale)
      group.add(dropIn)
      splatRef.current = dropIn
      if (pointsRef.current) pointsRef.current.visible = false
      if (meshRef.current) meshRef.current.visible = false
      setSplatLoading(false)
    } catch (err) {
      console.error('splat load error:', err)
      setSplatLoading(false)
      setSplatView(false)
    }
  }

  const toggleSplat = async () => {
    const next = !splatView
    setSplatView(next)
    if (next) {
      // Splat is mutually exclusive with the mesh view.
      setSmoothSurface(false)
      if (meshRef.current) meshRef.current.visible = false
      if (splatRef.current) {
        splatRef.current.visible = true
        if (pointsRef.current) pointsRef.current.visible = false
      } else {
        await loadSplat()
      }
    } else {
      if (splatRef.current) splatRef.current.visible = false
      if (pointsRef.current) pointsRef.current.visible = true
    }
  }

  const toggleSmooth = async () => {
    const next = !smoothSurface
    setSmoothSurface(next)
    if (next) {
      // Mesh is mutually exclusive with the splat view.
      if (splatView) {
        setSplatView(false)
        if (splatRef.current) splatRef.current.visible = false
      }
      if (meshRef.current) {
        meshRef.current.visible = true
        if (pointsRef.current) pointsRef.current.visible = false
      } else {
        await loadMesh()
      }
    } else {
      if (meshRef.current) meshRef.current.visible = false
      if (pointsRef.current) pointsRef.current.visible = true
    }
  }

  const rotateModel = (axis, degrees) => {
    const group = groupRef.current
    if (!group) return
    const rad = (degrees * Math.PI) / 180
    if (axis === 'x') group.rotation.x += rad
    if (axis === 'y') group.rotation.y += rad
    if (axis === 'z') group.rotation.z += rad
  }

  const resetRotation = () => {
    const group = groupRef.current
    if (group) group.rotation.set(0, 0, 0)
    // Also bring the camera back to the default framing of the wound.
    const camera = cameraRef.current
    const controls = controlsRef.current
    if (camera && controls) {
      camera.position.set(0, 0, DEFAULT_CAMERA_Z)
      controls.target.set(0, 0, 0)
      controls.update()
    }
  }

  return {
    mountRef,
    loading,
    error,
    smoothSurface,
    meshLoading,
    splatView,
    splatLoading,
    toggleSplat,
    toggleSmooth,
    rotateModel,
    resetRotation,
  }
}
