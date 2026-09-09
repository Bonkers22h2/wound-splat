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

export const tissueApi = {
  // The saved result for a scan, or null when it has not been analysed yet.
  get: async (scanId) => {
    const res = await fetch(`${API_BASE}/scans/${scanId}/tissue`)
    return res.ok ? res.json() : null
  },

  // box is { left, top, right, bottom } in pixels of the *original* frame,
  // not of the scaled <img> shown on screen. Returns the raw Response so
  // callers can surface the backend's message on 400/409/500.
  analyse: (scanId, box) =>
    fetch(`${API_BASE}/scans/${scanId}/tissue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(box),
    }),
}

// URL builders for assets referenced outside fetch (three.js loaders,
// <img> tags, and download links).
export const scanUrls = {
  // full=true fetches the complete unfiltered scene instead of the wound crop.
  ply: (scanId, full = false) => `${API_BASE}/scans/${scanId}/ply${full ? '?full=true' : ''}`,
  splat: (scanId) => `${API_BASE}/scans/${scanId}/splat`,
  mesh: (scanId) => `${API_BASE}/scans/${scanId}/mesh`,
  reportPdf: (scanId) => `${API_BASE}/reports/${scanId}/pdf`,

  // The frame the box is drawn on. This is the same frame the model
  // analyses - the backend picks it once, so the two cannot disagree.
  tissueFrame: (scanId) => `${API_BASE}/scans/${scanId}/tissue/frame`,
  // Cache-busted so a re-analysis shows the new overlay, not the old one.
  tissueOverlay: (scanId, version = '') =>
    `${API_BASE}/scans/${scanId}/tissue/overlay${version ? `?v=${version}` : ''}`,
}
