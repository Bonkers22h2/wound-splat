'use client'
import { useEffect, useState, useSyncExternalStore } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Navbar from '../components/Navbar'
import { Icon } from '../components/Icons'
import { dashboardApi } from '@/lib/api'
import {
  clearSession,
  getServerSessionSnapshot,
  getSessionSnapshot,
  logout,
  subscribeAuth,
} from '@/lib/auth'

export default function DashboardPage() {
  const router = useRouter()
  const session = useSyncExternalStore(
    subscribeAuth,
    getSessionSnapshot,
    getServerSessionSnapshot
  )

  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshTick, setRefreshTick] = useState(0)

  useEffect(() => {
    let active = true
    dashboardApi.getSummary()
      .then((data) => {
        if (!active) return
        setSummary(data)
        setError('')
      })
      .catch((err) => {
        if (!active) return
        if (err?.status === 401) {
          clearSession()
          router.replace('/login?reason=expired&next=/dashboard')
          return
        }
        setError(err?.message || 'Could not load dashboard metrics from the backend.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [router, refreshTick])

  const handleRefresh = () => {
    setLoading(true)
    setRefreshTick(t => t + 1)
  }

  const handleLogout = async () => {
    await logout()
    router.push('/login?loggedOut=1')
  }

  const patients = summary?.patients || []
  const assessments = summary?.assessments || []
  const stats = summary?.stats || {
    totalPatients: 0,
    totalAssessments: 0,
    completedAssessments: 0,
    withMeasurements: 0,
    queuedAssessments: 0,
    processingAssessments: 0,
    activeProcessing: 0,
    failedAssessments: 0,
  }

  const latestRendered = assessments.find(item => item.status === 'rendered')
  const previewScanId = latestRendered?.id || 'demo-scan-001'

  const assessmentCountByPatient = assessments.reduce((acc, scan) => {
    acc[scan.patient_id] = (acc[scan.patient_id] || 0) + 1
    return acc
  }, {})

  const shortcuts = [
    {
      href: '/patient',
      title: 'Patient Portal',
      description: 'Upload wound videos and check patient-facing scan status.',
      icon: 'patient',
    },
    {
      href: '/admin',
      title: 'Clinical Workspace',
      description: 'Monitor reconstruction queues and register new patients.',
      icon: 'activity',
    },
    {
      href: `/viewer/${previewScanId}`,
      title: '3D Wound Viewer',
      description: 'Inspect point clouds, smooth meshes, and calibrated metrics.',
      icon: 'eye',
    },
    {
      href: `/tissue/${previewScanId}`,
      title: 'Tissue Analysis',
      description: 'Select wound boundaries and review granulation, fibrin, and callus.',
      icon: 'layers',
    },
    {
      href: '/longitudinal',
      title: 'Longitudinal Review',
      description: 'Compare multi-visit healing deltas and volume trends.',
      icon: 'clock',
    },
  ]

  return (
    <>
      <Navbar />
      <main className="page">
        <div className="page-container">
          <div className="page-header">
            <div>
              <div className="eyebrow">Wound-Splat dashboard</div>
              <h1 className="page-title">
                {session ? `Welcome, ${session.fullName}` : 'Clinical overview'}
              </h1>
              <p className="page-subtitle">
                {session
                  ? `${session.role === 'clinician' ? 'Clinician' : 'Patient'} · ${session.clinic || 'Metro Care Clinic'}`
                  : 'Patient counts, recent wound assessments, and quick shortcuts across the system.'}
              </p>
            </div>
            <div className="dashboard-header-actions">
              {session && (
                <span className="status status-calibrated">
                  Clinician session
                </span>
              )}
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleRefresh}
                disabled={loading}
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </button>
              {session ? (
                <button type="button" className="btn btn-secondary" onClick={handleLogout}>
                  <Icon name="logout" size={16} />
                  Sign out
                </button>
              ) : (
                <Link href="/login" className="btn btn-primary">
                  <Icon name="lock" size={16} />
                  Sign in
                </Link>
              )}
            </div>
          </div>

          {error && (
            <div className="dashboard-banner notice notice-error" role="alert" style={{ marginBottom: '18px' }}>
              <div>
                <strong>Could not load dashboard data</strong>
                <span> · {error}</span>
              </div>
              <button type="button" className="btn btn-secondary" onClick={handleRefresh}>
                Retry connection
              </button>
            </div>
          )}

          <section aria-label="Patient and assessment summary metrics" className="grid-4" style={{ marginBottom: '22px' }}>
            <div className="metric-card">
              <div className="metric-head">
                <span>Total patients</span>
                <span className="metric-icon"><Icon name="patient" size={16} /></span>
              </div>
              <div className="metric-value">{loading && !summary ? '—' : stats.totalPatients}</div>
              <div className="metric-meta">Registered clinic records</div>
            </div>

            <div className="metric-card">
              <div className="metric-head">
                <span>Total assessments</span>
                <span className="metric-icon"><Icon name="file" size={16} /></span>
              </div>
              <div className="metric-value">{loading && !summary ? '—' : stats.totalAssessments}</div>
              <div className="metric-meta">
                {loading && !summary ? 'Loading…' : `${stats.withMeasurements} with measurements`}
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-head">
                <span>In progress</span>
                <span className="metric-icon"><Icon name="clock" size={16} /></span>
              </div>
              <div className="metric-value" style={{ color: '#0284C7' }}>
                {loading && !summary ? '—' : stats.activeProcessing}
              </div>
              <div className="metric-meta">
                {loading && !summary
                  ? 'Checking status…'
                  : `${stats.processingAssessments} processing · ${stats.queuedAssessments} queued`}
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-head">
                <span>Ready for review</span>
                <span className="metric-icon"><Icon name="activity" size={16} /></span>
              </div>
              <div className="metric-value" style={{ color: 'var(--teal)' }}>
                {loading && !summary ? '—' : stats.completedAssessments}
              </div>
              <div className="metric-meta">
                {stats.failedAssessments > 0
                  ? `${stats.failedAssessments} failed scan${stats.failedAssessments > 1 ? 's' : ''}`
                  : 'Rendered 3D models'}
              </div>
            </div>
          </section>

          <section aria-label="Shortcuts to main pages" style={{ marginBottom: '22px' }}>
            <div className="dashboard-section-head">
              <h2>Main pages</h2>
              <span className="helper">Jump directly to capture, review, or longitudinal tools</span>
            </div>
            <div className="shortcut-grid">
              {shortcuts.map(item => (
                <Link key={item.href} href={item.href} className="shortcut-card">
                  <div className="shortcut-top">
                    <span className="shortcut-icon"><Icon name={item.icon} size={18} /></span>
                    <span className="shortcut-arrow"><Icon name="arrowRight" size={16} /></span>
                  </div>
                  <strong>{item.title}</strong>
                  <p>{item.description}</p>
                </Link>
              ))}
            </div>
          </section>

          <section className="dashboard-split" aria-label="Patient and assessment summaries">
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Patient summary</h2>
                <Link href="/admin" className="dashboard-card-link">Open workspace</Link>
              </div>
              {patients.length === 0 ? (
                <div className="empty">
                  <div className="empty-icon"><Icon name="patient" size={20} /></div>
                  <strong>{loading ? 'Loading patients…' : 'No patients registered'}</strong>
                  <span className="helper">Register a patient in the Clinical Workspace to begin tracking scans.</span>
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Patient</th>
                        <th>Code</th>
                        <th>Assessments</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {patients.slice(0, 6).map(patient => (
                        <tr key={patient.id}>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span className="record-avatar">
                                {patient.name?.slice(0, 2).toUpperCase() || 'PT'}
                              </span>
                              <strong>{patient.name}</strong>
                            </div>
                          </td>
                          <td className="mono-code">{patient.patient_code}</td>
                          <td>{assessmentCountByPatient[patient.id] || 0}</td>
                          <td><span className="status status-rendered">Active</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Recent assessments</h2>
                <Link href="/longitudinal" className="dashboard-card-link">Compare visits</Link>
              </div>
              {assessments.length === 0 ? (
                <div className="empty">
                  <div className="empty-icon"><Icon name="activity" size={20} /></div>
                  <strong>{loading ? 'Loading assessments…' : 'No assessments yet'}</strong>
                  <span className="helper">Submitted wound videos will appear here with status and review links.</span>
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Assessment</th>
                        <th>Patient</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assessments.slice(0, 6).map(scan => (
                        <tr key={scan.id}>
                          <td>
                            <strong style={{ display: 'block' }}>{scan.video_filename}</strong>
                            <span className="muted" style={{ fontSize: '11px' }}>
                              {scan.created_at ? new Date(scan.created_at).toLocaleDateString() : '—'}
                            </span>
                          </td>
                          <td>
                            <span style={{ display: 'block', fontWeight: 600 }}>{scan.patient_name || 'Patient'}</span>
                            <span className="mono-code" style={{ fontSize: '11px' }}>{scan.patient_code || '—'}</span>
                          </td>
                          <td>
                            <span className={`status status-${scan.status}`}>{scan.status}</span>
                            {scan.status === 'processing' && (
                              <div className="progress-bar" style={{ marginTop: '6px', minWidth: '90px' }}>
                                <div style={{ width: `${scan.progress_percent || 0}%` }} />
                              </div>
                            )}
                          </td>
                          <td>
                            {scan.status === 'rendered' ? (
                              <div className="assessment-actions">
                                <Link href={`/viewer/${scan.id}`} className="dashboard-card-link">3D</Link>
                                <Link href={`/tissue/${scan.id}`} className="dashboard-card-link">Tissue</Link>
                              </div>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </>
  )
}
