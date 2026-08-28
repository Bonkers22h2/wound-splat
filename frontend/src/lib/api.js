// Central client for the FastAPI backend. All calls go through the Next.js
// /api rewrite (see next.config.ts), which proxies to the backend. Using the
// relative /api path keeps every request same-origin, so the app works both
// locally and behind a remote proxy (e.g. a cloud GPU pod) where an absolute
// localhost URL would resolve to the viewer's own machine, not the server.
const API_BASE = '/api'

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`)
  return res.json()
}

export const patientApi = {
  list: () => getJson('/patients'),

  // Returns the raw Response so callers can inspect res.ok and error details.
  create: (patient) =>
    fetch(`${API_BASE}/patients`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patient),
    }),
}

export const scanApi = {
  listForPatient: (patientId) => getJson(`/scans/patient/${patientId}`),
  adminQueue: () => getJson('/scans/admin/queue'),
  measurements: (scanId) => getJson(`/scans/${scanId}/measurements`),

  // referenceObject: known-size object in the video used for absolute-scale
  // calibration (e.g. 'card', 'coin:us_quarter'); omit/null when none.
  upload: async (patientId, file, referenceObject) => {
    const formData = new FormData()
    formData.append('file', file)
    if (referenceObject) formData.append('reference_object', referenceObject)
    const res = await fetch(`${API_BASE}/scans/upload/${patientId}`, {
      method: 'POST',
      body: formData,
    })
    return res.json()
  },
}

// URL builders for assets referenced outside fetch (three.js loaders,
// <img> tags, and download links).
export const scanUrls = {
  // full=true fetches the complete unfiltered scene instead of the wound crop.
  ply: (scanId, full = false) => `${API_BASE}/scans/${scanId}/ply${full ? '?full=true' : ''}`,
  splat: (scanId) => `${API_BASE}/scans/${scanId}/splat`,
  mesh: (scanId) => `${API_BASE}/scans/${scanId}/mesh`,
  reportPdf: (scanId) => `${API_BASE}/reports/${scanId}/pdf`,
}
