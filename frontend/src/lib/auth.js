// Client-side authentication & session store.
// Structured as async methods so Joseph's backend /api/auth/* endpoints
// (POST /api/auth/login, POST /api/auth/signup, POST /api/auth/logout,
// GET /api/auth/me) can replace the localStorage fallback cleanly.

const USERS_KEY = 'woundsplat_users'
const SESSION_KEY = 'woundsplat_session'
const AUTH_EVENT = 'woundsplat:auth-change'

export const DEMO_ACCOUNTS = [
  {
    id: 'user-clinician-001',
    fullName: 'Dr. Elena Santos',
    email: 'dr.santos@metrocare.ph',
    password: 'Clinic123!',
    role: 'clinician',
    clinic: 'Metro Care Clinic',
    patientCode: '',
  },
  {
    id: 'user-patient-001',
    fullName: 'Maria Santos',
    email: 'maria.santos@example.com',
    password: 'Patient123!',
    role: 'patient',
    clinic: 'Metro Care Clinic',
    patientCode: 'PT-001',
  },
]

let cachedRaw = undefined
let cachedSession = null

function notifyAuthChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_EVENT))
  }
}

function readStoredUsers() {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(USERS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function getAllUsers() {
  const stored = readStoredUsers()
  const knownEmails = new Set(stored.map(u => String(u.email || '').toLowerCase()))
  const merged = [...stored]
  for (const demo of DEMO_ACCOUNTS) {
    if (!knownEmails.has(demo.email.toLowerCase())) {
      merged.push(demo)
    }
  }
  return merged
}

function toPublicSession(user) {
  return {
    id: user.id,
    fullName: user.fullName,
    email: user.email,
    role: user.role,
    clinic: user.clinic || 'Metro Care Clinic',
    patientCode: user.patientCode || '',
    signedInAt: new Date().toISOString(),
  }
}

function writeSession(session) {
  if (typeof window === 'undefined') return
  const raw = JSON.stringify(session)
  window.localStorage.setItem(SESSION_KEY, raw)
  cachedRaw = raw
  cachedSession = session
  notifyAuthChanged()
}

export function getSessionSnapshot() {
  if (typeof window === 'undefined') return null
  const raw = window.localStorage.getItem(SESSION_KEY)
  if (raw === cachedRaw) return cachedSession
  cachedRaw = raw
  if (!raw) {
    cachedSession = null
    return null
  }
  try {
    cachedSession = JSON.parse(raw)
  } catch {
    cachedSession = null
  }
  return cachedSession
}

export function getServerSessionSnapshot() {
  return null
}

export function subscribeAuth(callback) {
  if (typeof window === 'undefined') return () => {}
  const handler = () => callback()
  window.addEventListener(AUTH_EVENT, handler)
  window.addEventListener('storage', handler)
  return () => {
    window.removeEventListener(AUTH_EVENT, handler)
    window.removeEventListener('storage', handler)
  }
}

export async function login({ email, password }) {
  // Future backend hook: replace with POST /api/auth/login
  await new Promise(resolve => setTimeout(resolve, 250))

  const normalizedEmail = String(email || '').trim().toLowerCase()
  const match = getAllUsers().find(
    user => String(user.email || '').trim().toLowerCase() === normalizedEmail
      && user.password === password
  )

  if (!match) {
    const err = new Error('Invalid email or password. Check your credentials and try again.')
    err.code = 'INVALID_CREDENTIALS'
    throw err
  }

  const session = toPublicSession(match)
  writeSession(session)
  return session
}

export async function signup({ fullName, email, password, role, clinic = '', patientCode = '' }) {
  // Future backend hook: replace with POST /api/auth/signup
  await new Promise(resolve => setTimeout(resolve, 300))

  const normalizedEmail = String(email || '').trim().toLowerCase()
  const users = getAllUsers()
  const exists = users.some(
    user => String(user.email || '').trim().toLowerCase() === normalizedEmail
  )

  if (exists) {
    const err = new Error('An account with this email address already exists.')
    err.code = 'EMAIL_EXISTS'
    throw err
  }

  const newUser = {
    id: `user-${Date.now()}`,
    fullName: String(fullName || '').trim(),
    email: normalizedEmail,
    password: String(password || ''),
    role: role === 'patient' ? 'patient' : 'clinician',
    clinic: String(clinic || '').trim() || 'Metro Care Clinic',
    patientCode: String(patientCode || '').trim().toUpperCase(),
  }

  if (typeof window !== 'undefined') {
    const stored = readStoredUsers()
    window.localStorage.setItem(USERS_KEY, JSON.stringify([...stored, newUser]))
  }

  const session = toPublicSession(newUser)
  writeSession(session)
  return session
}

export async function logout() {
  // Future backend hook: replace with POST /api/auth/logout
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(SESSION_KEY)
    cachedRaw = null
    cachedSession = null
    notifyAuthChanged()
  }
}
