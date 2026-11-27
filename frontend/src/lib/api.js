// Central client for the FastAPI backend. All calls go through the Next.js
// /api rewrite (see next.config.ts), which proxies to the backend. Using the
// relative /api path keeps every request same-origin, so the app works both
// locally and behind a remote proxy (e.g. a cloud GPU pod) where an absolute
// localhost URL would resolve to the viewer's own machine, not the server.
const API_BASE = '/api'

export function extractErrorMessage(payload, fallback = 'Request failed. Please try again.') {
  if (!payload) return fallback
  if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail
  if (Array.isArray(payload.detail)) {
    const messages = payload.detail
      .map(item => (typeof item?.msg === 'string' ? item.msg.replace(/^Value error,\s*/i, '') : null))
      .filter(Boolean)
    if (messages.length > 0) return messages.join(' ')
  }
  return fallback
}

function apiError(message, status = 0) {
  const err = new Error(message)
  err.status = status
  return err
}

async function requestJson(path, options = {}, { fallback, allow404 = false } = {}) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...options })
  } catch {
    throw apiError('Could not connect to the backend server. Check that the API is running and try again.')
  }

  if (res.status === 204 || (allow404 && res.status === 404)) return null

  const payload = await res.json().catch(() => null)
  if (!res.ok) {
    const defaultMsg = res.status === 401
      ? 'Your session has expired. Please sign in again.'
      : (fallback || `Request failed with status ${res.status}.`)
    throw apiError(extractErrorMessage(payload, defaultMsg), res.status)
  }
  return payload
}

const jsonPost = (path, body) =>
  requestJson(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const authApi = {
  signup: ({ fullName, email, password }) =>
    jsonPost('/auth/signup', { full_name: fullName, email, password }),
  login: ({ email, password }) => jsonPost('/auth/login', { email, password }),
  me: () => requestJson('/auth/me'),
  logout: () => requestJson('/auth/logout', { method: 'POST' }),
}

export const patientApi = {
  list: () => requestJson('/patients'),

  // Returns the raw Response so callers can inspect res.ok and error details.
  create: (patient) =>
    fetch(`${API_BASE}/patients`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patient),
    }),
}

export const scanApi = {
  listForPatient: (patientId) => requestJson(`/scans/patient/${patientId}`),
  adminQueue: () => requestJson('/scans/admin/queue'),
  adminSummary: () => requestJson('/scans/admin/summary'),
  measurements: (scanId) => requestJson(`/scans/${scanId}/measurements`),

  // referenceObject: known-size object in the video used for absolute-scale
  // calibration (e.g. 'card', 'coin:us_quarter'); omit/null when none.
  upload: (patientId, file, referenceObject) => {
    const formData = new FormData()
    formData.append('file', file)
    if (referenceObject) formData.append('reference_object', referenceObject)
    return requestJson(
      `/scans/upload/${patientId}`,
      { method: 'POST', body: formData },
      { fallback: 'Upload failed. Please try again.' }
    )
  },
}

export const tissueApi = {
  // The saved result for a scan, or null when it has not been analysed yet.
  get: (scanId) => requestJson(`/scans/${scanId}/tissue`, {}, { allow404: true }),

  // box is { left, top, right, bottom } in pixels of the *original* frame,
  // not of the scaled <img> shown on screen. Returns the raw Response so
  // callers can surface the backend's message on 400/409/500.
  analyse: (scanId, box) =>
    fetch(`${API_BASE}/scans/${scanId}/tissue`, {
      method: 'POST',
      credentials: 'include',
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

export const dashboardApi = {
  getSummary: async () => {
    const [summary, patients, queue] = await Promise.all([
      scanApi.adminSummary(),
      patientApi.list(),
      scanApi.adminQueue(),
    ])
    if (!summary || !Array.isArray(patients) || !Array.isArray(queue)) {
      throw apiError('Unexpected dashboard response format.')
    }
    const patientMap = new Map(patients.map(p => [p.id, p]))
    const assessments = queue.map(scan => {
      const patient = patientMap.get(scan.patient_id)
      return {
        ...scan,
        patient_name: patient?.name || 'Patient record',
        patient_code: patient?.patient_code || scan.patient_id?.slice(0, 8) || '—',
      }
    })
    const assessmentSummary = summary.assessment_summary || {}
    const processingStatus = summary.processing_status || {}
    const queued = processingStatus.queued ?? 0
    const processing = processingStatus.processing ?? 0
    return {
      patients,
      assessments,
      stats: {
        totalPatients: summary.patient_count ?? patients.length,
        totalAssessments: assessmentSummary.total ?? assessments.length,
        completedAssessments: assessmentSummary.completed ?? 0,
        withMeasurements: assessmentSummary.with_measurements ?? 0,
        queuedAssessments: queued,
        processingAssessments: processing,
        activeProcessing: queued + processing,
        failedAssessments: processingStatus.failed ?? 0,
      },
    }
  },
}
