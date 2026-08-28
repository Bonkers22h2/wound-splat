// Explicit upload proxy for wound videos.
//
// Every other /api/* call is handled by the catch-all rewrite in next.config.ts,
// but that rewrite resets the socket (ECONNRESET) on large multipart bodies, so
// the video upload needs a dedicated route handler. It runs server-side on the
// Next process, which sits on the same host as the backend, so it can forward to
// localhost:8000 directly (a client-side call to localhost would hit the user's
// own machine when the app is served through a remote proxy).
//
// This file-system route takes precedence over the afterFiles rewrite, so only
// the upload path is intercepted; all other /api/* calls still proxy as before.

export const runtime = 'nodejs'

const BACKEND_URL = 'http://localhost:8000'

export async function POST(request, { params }) {
  const { patientId } = await params

  // Re-send the parsed multipart form; fetch rebuilds a valid multipart body
  // (with boundary) so FastAPI's UploadFile + Form fields parse unchanged.
  const formData = await request.formData()

  let res
  try {
    res = await fetch(`${BACKEND_URL}/scans/upload/${patientId}`, {
      method: 'POST',
      body: formData,
    })
  } catch (err) {
    return Response.json(
      { detail: `Could not reach backend: ${err?.message ?? err}` },
      { status: 502 },
    )
  }

  const body = await res.text()
  return new Response(body, {
    status: res.status,
    headers: { 'content-type': res.headers.get('content-type') || 'application/json' },
  })
}
