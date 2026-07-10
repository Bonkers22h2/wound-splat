// Central client for the FastAPI backend. All calls go through the Next.js
// /api rewrite (see next.config.ts), which proxies to the backend.
const API_BASE = '/api'

// Video uploads (up to 100MB) go straight to the backend instead of through
// the dev-server proxy, so large request bodies are not buffered by Next.
const BACKEND_DIRECT_URL = 'http://localhost:8000'

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`)
  return res.json()
}

export const patientApi = {
  list: () => getJson('/patients/'),

  // Returns the raw Response so callers can inspect res.ok and error details.
  create: (patient) =>
    fetch(`${API_BASE}/patients/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patient),
    }),
}

export const scanApi = {
  listForPatient: (patientId) => getJson(`/scans/patient/${patientId}`),
  adminQueue: () => getJson('/scans/admin/queue'),
  measurements: (scanId) => getJson(`/scans/${scanId}/measurements`),
  depthMaps: (scanId) => getJson(`/scans/${scanId}/depths`),

  // referenceObject: known-size object in the video used for absolute-scale
  // calibration (e.g. 'card', 'coin:us_quarter'); omit/null when none.
  upload: async (patientId, file, referenceObject) => {
    const formData = new FormData()
    formData.append('file', file)
    if (referenceObject) formData.append('reference_object', referenceObject)
    const res = await fetch(`${BACKEND_DIRECT_URL}/scans/upload/${patientId}`, {
      method: 'POST',
      body: formData,
    })
    return res.json()
  },
}

// URL builders for assets referenced outside fetch (three.js loaders,
// <img> tags, and download links).
export const scanUrls = {
  ply: (scanId) => `${API_BASE}/scans/${scanId}/ply`,
  splat: (scanId) => `${API_BASE}/scans/${scanId}/splat`,
  mesh: (scanId) => `${API_BASE}/scans/${scanId}/mesh`,
  depthImage: (scanId, name) => `${API_BASE}/scans/${scanId}/depth/${name}`,
  reportPdf: (scanId) => `${API_BASE}/reports/${scanId}/pdf`,
}
