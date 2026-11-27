'use client'
import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import Navbar from '../components/Navbar'
import { Icon } from '../components/Icons'
import { signup } from '@/lib/auth'
import { getPasswordChecks, validateSignupForm } from '@/lib/authValidation.mjs'

export default function SignupPage() {
  const router = useRouter()

  const role = 'clinician'
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [touched, setTouched] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')

  const validation = validateSignupForm({
    fullName,
    email,
    password,
    confirmPassword,
    role,
    acceptedTerms,
  })
  const checks = getPasswordChecks(password)
  const fieldError = (name) => ((submitted || touched[name]) ? validation.errors[name] : '')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitted(true)
    setFormError('')
    if (!validation.valid || submitting) return

    setSubmitting(true)
    try {
      await signup({
        fullName,
        email,
        password,
      })
      router.push('/dashboard')
    } catch (err) {
      setFormError(err?.message || 'Could not create your account. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const checkItems = [
    ['minLength', 'At least 12 characters'],
    ['hasUpper', 'One uppercase letter'],
    ['hasLower', 'One lowercase letter'],
    ['hasNumber', 'One number'],
  ]

  return (
    <>
      <Navbar />
      <main className="auth-shell">
        <section className="auth-panel">
          <div className="auth-form-wrap">
            <div className="eyebrow">Create account</div>
            <h1 className="auth-title">Join Wound-Splat</h1>
            <p className="helper" style={{ marginBottom: '20px' }}>
              Set up clinician access to monitor wound reconstructions and assessments.
            </p>

            <div className="role-grid" role="group" aria-label="Account role" style={{ marginBottom: '18px' }}>
              <button
                type="button"
                className={`role-card ${role === 'clinician' ? 'active' : ''}`}
                aria-pressed={role === 'clinician'}
              >
                <strong>Clinician</strong>
                <span>Manage patient queues, review 3D models, and compare visits.</span>
              </button>
              <button
                type="button"
                className={`role-card ${role === 'patient' ? 'active' : ''}`}
                disabled
                aria-pressed={role === 'patient'}
              >
                <strong>Patient</strong>
                <span>Patient accounts are not available yet. Registration currently supports clinicians only.</span>
              </button>
            </div>
            {fieldError('role') && (
              <span className="field-error" style={{ marginBottom: '12px' }}>{fieldError('role')}</span>
            )}

            <form noValidate onSubmit={handleSubmit}>
              <div className="field" style={{ marginBottom: '14px' }}>
                <label className="label" htmlFor="signup-name">Full name</label>
                <input
                  id="signup-name"
                  name="fullName"
                  type="text"
                  autoComplete="name"
                  className={`input ${fieldError('fullName') ? 'input-error' : ''}`}
                  value={fullName}
                  onChange={(e) => { setFullName(e.target.value); setFormError('') }}
                  onBlur={() => setTouched(prev => ({ ...prev, fullName: true }))}
                  placeholder={role === 'clinician' ? 'e.g. Dr. Elena Santos' : 'e.g. Maria Santos'}
                  aria-invalid={Boolean(fieldError('fullName'))}
                  aria-describedby={fieldError('fullName') ? 'signup-name-error' : undefined}
                />
                {fieldError('fullName') && (
                  <span id="signup-name-error" className="field-error">{fieldError('fullName')}</span>
                )}
              </div>

              <div className="grid-2" style={{ marginBottom: '14px' }}>
                <div className="field">
                  <label className="label" htmlFor="signup-email">Email address</label>
                  <input
                    id="signup-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    className={`input ${fieldError('email') ? 'input-error' : ''}`}
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setFormError('') }}
                    onBlur={() => setTouched(prev => ({ ...prev, email: true }))}
                    placeholder="name@clinic.ph"
                    aria-invalid={Boolean(fieldError('email'))}
                    aria-describedby={fieldError('email') ? 'signup-email-error' : undefined}
                  />
                  {fieldError('email') && (
                    <span id="signup-email-error" className="field-error">{fieldError('email')}</span>
                  )}
                </div>

              </div>

              <div className="field" style={{ marginBottom: '12px' }}>
                <label className="label" htmlFor="signup-password">Password</label>
                <div className="password-wrap">
                  <input
                    id="signup-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    className={`input ${fieldError('password') ? 'input-error' : ''}`}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setFormError('') }}
                    onBlur={() => setTouched(prev => ({ ...prev, password: true }))}
                    placeholder="Create a strong password"
                    aria-invalid={Boolean(fieldError('password'))}
                    aria-describedby={fieldError('password') ? 'signup-password-error' : 'signup-password-rules'}
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword(prev => !prev)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    <Icon name={showPassword ? 'eyeOff' : 'eye'} size={16} />
                  </button>
                </div>
                {fieldError('password') && (
                  <span id="signup-password-error" className="field-error">{fieldError('password')}</span>
                )}
                <div id="signup-password-rules" className="password-checklist" aria-label="Password requirements">
                  {checkItems.map(([key, label]) => (
                    <span key={key} className={`check-item ${checks[key] ? 'met' : ''}`}>
                      <Icon name="check" size={12} />
                      {label}
                    </span>
                  ))}
                </div>
              </div>

              <div className="field" style={{ marginBottom: '14px' }}>
                <label className="label" htmlFor="signup-confirm">Confirm password</label>
                <div className="password-wrap">
                  <input
                    id="signup-confirm"
                    name="confirmPassword"
                    type={showConfirm ? 'text' : 'password'}
                    autoComplete="new-password"
                    className={`input ${fieldError('confirmPassword') ? 'input-error' : ''}`}
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); setFormError('') }}
                    onBlur={() => setTouched(prev => ({ ...prev, confirmPassword: true }))}
                    placeholder="Re-enter your password"
                    aria-invalid={Boolean(fieldError('confirmPassword'))}
                    aria-describedby={fieldError('confirmPassword') ? 'signup-confirm-error' : undefined}
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowConfirm(prev => !prev)}
                    aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
                  >
                    <Icon name={showConfirm ? 'eyeOff' : 'eye'} size={16} />
                  </button>
                </div>
                {fieldError('confirmPassword') && (
                  <span id="signup-confirm-error" className="field-error">{fieldError('confirmPassword')}</span>
                )}
              </div>

              <div style={{ marginBottom: '18px' }}>
                <label className="checkbox-field" htmlFor="signup-terms">
                  <input
                    id="signup-terms"
                    type="checkbox"
                    checked={acceptedTerms}
                    onChange={(e) => {
                      setAcceptedTerms(e.target.checked)
                      setTouched(prev => ({ ...prev, acceptedTerms: true }))
                    }}
                  />
                  <span>
                    I understand Wound-Splat is a clinical decision-support tool and not an automated diagnosis system.
                  </span>
                </label>
                {fieldError('acceptedTerms') && (
                  <span className="field-error" style={{ marginTop: '6px' }}>{fieldError('acceptedTerms')}</span>
                )}
              </div>

              {formError && (
                <div className="notice notice-error" role="alert" style={{ marginBottom: '16px' }}>
                  {formError}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary btn-block"
                disabled={submitting}
              >
                <Icon name="shield" size={16} />
                {submitting ? 'Creating account…' : 'Create account'}
              </button>
            </form>

            <p className="auth-switch helper">
              Already have an account?{' '}
              <Link href="/login" className="auth-inline-link">Sign in</Link>
            </p>
          </div>
        </section>

        <aside className="auth-aside">
          <div className="auth-aside-brand">
            <span className="brand-mark">
              <Image src="/wound-splat-logo.png" alt="" fill sizes="38px" />
            </span>
            <span>Wound-Splat</span>
          </div>
          <div>
            <div className="auth-aside-kicker">Structured care workflow</div>
            <h2>Track every wound assessment from capture to review.</h2>
            <p className="auth-aside-copy">
              Built for coordinated diabetic foot ulcer documentation with calibrated 3D views and tissue breakdowns.
            </p>
          </div>
          <div className="auth-steps">
            {[
              ['01', 'Patients', 'Organized records & upload status'],
              ['02', 'Assessments', 'Queue progress & calibration flags'],
              ['03', 'Shortcuts', 'Direct access to 3D & tissue views'],
            ].map(([num, title, desc]) => (
              <div key={num} className="auth-step-item">
                <span>{num}</span>
                <strong>{title}</strong>
                <p>{desc}</p>
              </div>
            ))}
          </div>
        </aside>
      </main>
    </>
  )
}
