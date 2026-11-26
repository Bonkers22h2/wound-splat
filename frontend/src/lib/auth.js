// Client-side session store synced with FastAPI's HttpOnly cookie auth
// (/api/auth/signup, /api/auth/login, /api/auth/me, /api/auth/logout).
// FastAPI owns the session cookie; this module caches the public doctor profile.

import { authApi } from './api'

const listeners = new Set()
let currentSession = null
let hasHydrated = false
let pendingHydration = null

function notify() {
  for (const listener of listeners) listener()
}

function toSession(doctor) {
  if (!doctor) return null
  return {
    id: doctor.id,
    fullName: doctor.full_name,
    email: doctor.email,
    role: 'clinician',
    clinic: 'Metro Care Clinic',
  }
}

function setSession(nextSession) {
  currentSession = nextSession
  hasHydrated = true
  notify()
}

export function getSessionSnapshot() {
  return currentSession
}

export function getServerSessionSnapshot() {
  return null
}

export function subscribeAuth(callback) {
  listeners.add(callback)
  return () => listeners.delete(callback)
}

export function clearSession() {
  setSession(null)
}

export async function hydrateSession() {
  if (hasHydrated) return currentSession
  if (pendingHydration) return pendingHydration

  pendingHydration = authApi.me()
    .then((doctor) => {
      const session = toSession(doctor)
      setSession(session)
      return session
    })
    .catch((err) => {
      if (err?.status === 401) {
        setSession(null)
        return null
      }
      throw err
    })
    .finally(() => {
      pendingHydration = null
    })

  return pendingHydration
}

export async function login({ email, password }) {
  const session = toSession(await authApi.login({ email, password }))
  setSession(session)
  return session
}

export async function signup({ fullName, email, password }) {
  await authApi.signup({ fullName, email, password })
  // Signup returns 201 without setting a cookie, so log in right after.
  return login({ email, password })
}

export async function logout() {
  try {
    await authApi.logout()
  } finally {
    setSession(null)
  }
}
