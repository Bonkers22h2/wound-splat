export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export function validateEmail(email) {
  const trimmed = String(email || '').trim()
  if (!trimmed) return 'Email address is required.'
  if (!EMAIL_REGEX.test(trimmed)) return 'Enter a valid email address (e.g. name@clinic.ph).'
  return null
}

export function getPasswordChecks(password) {
  const value = String(password || '')
  return {
    minLength: value.length >= 12,
    hasUpper: /[A-Z]/.test(value),
    hasLower: /[a-z]/.test(value),
    hasNumber: /\d/.test(value),
  }
}

export function validateLoginForm({ email, password }) {
  const errors = {}

  const emailError = validateEmail(email)
  if (emailError) errors.email = emailError

  if (!String(password || '')) {
    errors.password = 'Password is required.'
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  }
}

export function validateSignupForm({
  fullName,
  email,
  password,
  confirmPassword,
  role,
  acceptedTerms,
}) {
  const errors = {}

  const trimmedName = String(fullName || '').trim().replace(/\s+/g, ' ')
  if (!trimmedName) {
    errors.fullName = 'Full name is required.'
  } else if (trimmedName.length < 2) {
    errors.fullName = 'Full name must be at least 2 characters.'
  }

  const emailError = validateEmail(email)
  if (emailError) errors.email = emailError

  const rawPassword = String(password || '')
  const checks = getPasswordChecks(rawPassword)
  if (!rawPassword) {
    errors.password = 'Password is required.'
  } else if (!checks.minLength) {
    errors.password = 'Password must be at least 12 characters long.'
  } else if (!checks.hasUpper) {
    errors.password = 'Password must include at least one uppercase letter.'
  } else if (!checks.hasLower) {
    errors.password = 'Password must include at least one lowercase letter.'
  } else if (!checks.hasNumber) {
    errors.password = 'Password must include at least one number.'
  }

  const rawConfirm = String(confirmPassword || '')
  if (!rawConfirm) {
    errors.confirmPassword = 'Please confirm your password.'
  } else if (rawConfirm !== rawPassword) {
    errors.confirmPassword = 'Passwords do not match.'
  }

  if (role !== 'clinician') {
    errors.role = 'Only clinician registration is currently supported.'
  }

  if (acceptedTerms !== true) {
    errors.acceptedTerms = 'Please acknowledge the clinical workspace privacy notice.'
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  }
}

export function sanitizeNextPath(next) {
  if (typeof next !== 'string') return '/dashboard'
  const trimmed = next.trim()
  if (!trimmed.startsWith('/') || trimmed.startsWith('//')) {
    return '/dashboard'
  }
  return trimmed
}
