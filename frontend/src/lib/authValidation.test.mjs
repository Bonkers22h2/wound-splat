import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  getPasswordChecks,
  sanitizeNextPath,
  validateEmail,
  validateLoginForm,
  validateSignupForm,
} from './authValidation.mjs'

describe('validateEmail', () => {
  it('accepts valid trimmed emails', () => {
    assert.equal(validateEmail('dr.santos@metrocare.ph'), null)
    assert.equal(validateEmail('  maria.santos@example.com  '), null)
  })

  it('rejects missing or malformed emails', () => {
    assert.equal(validateEmail(''), 'Email address is required.')
    assert.equal(validateEmail('   '), 'Email address is required.')
    assert.match(validateEmail('not-an-email'), /valid email/i)
    assert.match(validateEmail('user@domain'), /valid email/i)
  })
})

describe('getPasswordChecks', () => {
  it('reports individual password strength flags', () => {
    assert.deepEqual(getPasswordChecks('abc'), {
      minLength: false,
      hasUpper: false,
      hasLower: true,
      hasNumber: false,
    })
    assert.deepEqual(getPasswordChecks('Clinic123!'), {
      minLength: true,
      hasUpper: true,
      hasLower: true,
      hasNumber: true,
    })
  })
})

describe('validateLoginForm', () => {
  it('passes with valid email and non-empty password', () => {
    const result = validateLoginForm({
      email: 'dr.santos@metrocare.ph',
      password: 'secret',
    })
    assert.equal(result.valid, true)
    assert.deepEqual(result.errors, {})
  })

  it('returns field errors when email or password is invalid', () => {
    const result = validateLoginForm({ email: 'bad', password: '' })
    assert.equal(result.valid, false)
    assert.ok(result.errors.email)
    assert.equal(result.errors.password, 'Password is required.')
  })
})

describe('validateSignupForm', () => {
  const validPayload = {
    fullName: 'Elena Santos',
    email: 'elena@metrocare.ph',
    password: 'Clinic123!',
    confirmPassword: 'Clinic123!',
    role: 'clinician',
    acceptedTerms: true,
  }

  it('passes for complete valid signup data', () => {
    const result = validateSignupForm(validPayload)
    assert.equal(result.valid, true)
    assert.deepEqual(result.errors, {})
  })

  it('rejects short fullName, weak passwords, and mismatched confirmation', () => {
    const shortName = validateSignupForm({ ...validPayload, fullName: 'A' })
    assert.equal(shortName.valid, false)
    assert.match(shortName.errors.fullName, /2 characters/i)

    const shortPass = validateSignupForm({ ...validPayload, password: 'Ab1', confirmPassword: 'Ab1' })
    assert.equal(shortPass.valid, false)
    assert.match(shortPass.errors.password, /8 characters/i)

    const noUpper = validateSignupForm({ ...validPayload, password: 'clinic123', confirmPassword: 'clinic123' })
    assert.equal(noUpper.valid, false)
    assert.match(noUpper.errors.password, /uppercase/i)

    const noLower = validateSignupForm({ ...validPayload, password: 'CLINIC123', confirmPassword: 'CLINIC123' })
    assert.equal(noLower.valid, false)
    assert.match(noLower.errors.password, /lowercase/i)

    const noNumber = validateSignupForm({ ...validPayload, password: 'ClinicPass', confirmPassword: 'ClinicPass' })
    assert.equal(noNumber.valid, false)
    assert.match(noNumber.errors.password, /number/i)

    const mismatch = validateSignupForm({ ...validPayload, confirmPassword: 'Different123!' })
    assert.equal(mismatch.valid, false)
    assert.equal(mismatch.errors.confirmPassword, 'Passwords do not match.')
  })

  it('rejects invalid role and unchecked terms', () => {
    const badRole = validateSignupForm({ ...validPayload, role: 'superadmin' })
    assert.equal(badRole.valid, false)
    assert.ok(badRole.errors.role)

    const noTerms = validateSignupForm({ ...validPayload, acceptedTerms: false })
    assert.equal(noTerms.valid, false)
    assert.ok(noTerms.errors.acceptedTerms)
  })
})

describe('sanitizeNextPath', () => {
  it('allows safe relative paths and rejects external or protocol-relative paths', () => {
    assert.equal(sanitizeNextPath('/admin'), '/admin')
    assert.equal(sanitizeNextPath('/viewer/demo-scan-001'), '/viewer/demo-scan-001')
    assert.equal(sanitizeNextPath('//evil.com'), '/dashboard')
    assert.equal(sanitizeNextPath('https://evil.com'), '/dashboard')
    assert.equal(sanitizeNextPath(null), '/dashboard')
  })
})
