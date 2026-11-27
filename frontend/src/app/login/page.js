'use client'
import { Suspense, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter, useSearchParams } from 'next/navigation'
import Navbar from '../components/Navbar'
import { Icon } from '../components/Icons'
import { login } from '@/lib/auth'
import { sanitizeNextPath, validateLoginForm } from '@/lib/authValidation.mjs'

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const reason = searchParams.get('reason')
  const loggedOut = searchParams.get('loggedOut') === '1'
  const nextPath = sanitizeNextPath(searchParams.get('next'))

  const [role, setRole] = useState('clinician')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [touched, setTouched] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')

  const validation = validateLoginForm({ email, password })
  const fieldError = (name) => ((submitted || touched[name]) ? validation.errors[name] : '')

  const handleRoleSelect = (nextRole) => {
    setRole(nextRole)
    setFormError('')
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitted(true)
    setFormError('')
    if (!validation.valid || submitting) return

    setSubmitting(true)
    try {
      await login({ email, password })
      router.push(nextPath)
    } catch (err) {
      setFormError(err?.message || 'Unable to sign in right now. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="auth-form-wrap">
          <div className="eyebrow">Account access</div>
          <h1 className="auth-title">Sign in to Wound-Splat</h1>
          <p className="helper" style={{ marginBottom: '20px' }}>
            Access patient summaries, 3D wound models, and longitudinal assessments.
          </p>

          {reason === 'expired' && (
            <div className="notice notice-warning" role="status" style={{ marginBottom: '16px' }}>
              Your session has expired. Please sign in again.
            </div>
          )}

          {loggedOut && (
            <div className="notice notice-success" role="status" style={{ marginBottom: '16px' }}>
              You have been signed out safely.
            </div>
          )}

          <div className="role-grid" role="group" aria-label="Account role preference" style={{ marginBottom: '18px' }}>
            <button
              type="button"
              className={`role-card ${role === 'clinician' ? 'active' : ''}`}
              onClick={() => handleRoleSelect('clinician')}
              aria-pressed={role === 'clinician'}
            >
              <strong>Clinician</strong>
              <span>Review 3D reconstructions, measurements, and patient queues.</span>
            </button>
            <button
              type="button"
              className={`role-card ${role === 'patient' ? 'active' : ''}`}
              onClick={() => handleRoleSelect('patient')}
              aria-pressed={role === 'patient'}
            >
              <strong>Patient</strong>
              <span>Upload wound videos and follow healing updates over time.</span>
            </button>
          </div>

          <form noValidate onSubmit={handleSubmit}>
            <div className="field" style={{ marginBottom: '14px' }}>
              <label className="label" htmlFor="login-email">Email address</label>
              <input
                id="login-email"
                name="email"
                type="email"
                autoComplete="email"
                className={`input ${fieldError('email') ? 'input-error' : ''}`}
                value={email}
                onChange={(e) => { setEmail(e.target.value); setFormError('') }}
                onBlur={() => setTouched(prev => ({ ...prev, email: true }))}
                placeholder={role === 'clinician' ? 'dr.santos@metrocare.ph' : 'maria.santos@example.com'}
                aria-invalid={Boolean(fieldError('email'))}
                aria-describedby={fieldError('email') ? 'login-email-error' : undefined}
              />
              {fieldError('email') && (
                <span id="login-email-error" className="field-error">{fieldError('email')}</span>
              )}
            </div>

            <div className="field" style={{ marginBottom: '18px' }}>
              <label className="label" htmlFor="login-password">Password</label>
              <div className="password-wrap">
                <input
                  id="login-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  className={`input ${fieldError('password') ? 'input-error' : ''}`}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setFormError('') }}
                  onBlur={() => setTouched(prev => ({ ...prev, password: true }))}
                  placeholder="Enter your password"
                  aria-invalid={Boolean(fieldError('password'))}
                  aria-describedby={fieldError('password') ? 'login-password-error' : undefined}
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
                <span id="login-password-error" className="field-error">{fieldError('password')}</span>
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
              <Icon name="lock" size={16} />
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="auth-demo-box">
            <div className="auth-demo-head">
              <strong>Authenticated clinician access</strong>
              <span>Sessions are verified by FastAPI using an HttpOnly cookie (12-hour limit).</span>
            </div>
          </div>

          <p className="auth-switch helper">
            New to Wound-Splat?{' '}
            <Link href="/signup" className="auth-inline-link">Create an account</Link>
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
          <div className="auth-aside-kicker">Clinical 3D monitoring</div>
          <h2>Calibrated wound review built for clinical teams.</h2>
          <p className="auth-aside-copy">
            Sign in to view reconstruction progress, calibrated geometry, tissue composition, and visit-over-visit healing trends.
          </p>
        </div>
        <div className="auth-steps">
          {[
            ['01', 'Capture', 'Smartphone video with scale reference'],
            ['02', 'Reconstruct', 'COLMAP + 3D Gaussian Splatting'],
            ['03', 'Assess', 'Measurements, tissue & history'],
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
  )
}

export default function LoginPage() {
  return (
    <>
      <Navbar />
      <Suspense fallback={
        <main className="page">
          <div className="page-container">
            <div className="empty">Loading sign-in form…</div>
          </div>
        </main>
      }>
        <LoginContent />
      </Suspense>
    </>
  )
}
