'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import Navbar from '../components/Navbar'
import { Icon } from '../components/Icons'
import { patientApi, scanApi } from '@/lib/api'
import { DEMO_PATIENT, DEMO_QUEUE } from '@/lib/demo'

export default function AdminPage() {
  const [queue, setQueue] = useState([])
  const [patients, setPatients] = useState([])
  const [newPatient, setNewPatient] = useState({ name:'', patient_code:'' })
  const [message, setMessage] = useState('')
  const [tab, setTab] = useState('queue')
  const [query, setQuery] = useState('')

  const loadQueue = async () => {
    try { setQueue(await scanApi.adminQueue()) }
    catch { setQueue(DEMO_QUEUE) }
  }
  const loadPatients = async () => {
    try { setPatients(await patientApi.list()) }
    catch { setPatients([DEMO_PATIENT]) }
  }

  const createPatient = async () => {
    if (!newPatient.name || !newPatient.patient_code) return
    try {
      const res = await patientApi.create(newPatient)
      if (res.ok) {
        setMessage(`Patient ${newPatient.patient_code} created successfully.`)
        setNewPatient({ name:'', patient_code:'' })
        loadPatients()
      } else {
        const err = await res.json()
        setMessage(err.detail || 'Error creating patient.')
      }
    } catch { setMessage('Could not connect to the server.') }
  }

  useEffect(() => {
    loadQueue()
    loadPatients()
    const interval = setInterval(loadQueue, 5000)
    return () => clearInterval(interval)
  }, [])

  const processing = queue.filter(s => s.status === 'processing').length
  const rendered = queue.filter(s => s.status === 'rendered').length
  const queued = queue.filter(s => s.status === 'queued').length
  const filteredPatients = patients.filter(p =>
    `${p.name} ${p.patient_code}`.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <>
      <Navbar />
      <main className="page">
        <div className="page-container">
          <div className="page-header">
            <div>
              <div className="eyebrow">Clinical workspace</div>
              <h1 className="page-title">Good morning, Dr. Santos</h1>
              <p className="page-subtitle">Monitor scans and support patient wound care.</p>
            </div>
            <div style={{ display:'flex', alignItems:'center', gap:'8px' }}>
              <Link href="/longitudinal" className="btn btn-primary" style={{ minHeight:'40px' }}>Open longitudinal review</Link>
              <div className="status status-calibrated">GPU active</div>
            </div>
          </div>

          <div className="grid-4" style={{ marginBottom:'18px' }}>
            <Stat label="In processing" value={processing} meta="Active reconstruction" tone="#0284C7" />
            <Stat label="Queued" value={queued} meta="Waiting to start" tone="#0F766E" />
            <Stat label="Completed" value={rendered} meta="Ready for review" tone="#10B981" />
            <Stat label="Patients" value={patients.length} meta="Registered records" tone="#0F172A" />
          </div>

          <div className="tabs" style={{ marginBottom:'18px' }}>
            {[
              ['queue','activity','Processing queue'],['patients','patient','Patients'],['register','plus','Register patient'],
            ].map(([key,icon,label]) => (
              <button key={key} className={`tab ${tab === key ? 'active' : ''}`} onClick={() => setTab(key)} style={{ display:'flex', alignItems:'center', gap:'7px' }}>
                <Icon name={icon} size={15} />{label}
              </button>
            ))}
          </div>

          {tab === 'queue' && (
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Processing queue</h2>
                <button className="btn btn-secondary" onClick={loadQueue} style={{ minHeight:'36px', padding:'7px 12px' }}>Refresh</button>
              </div>
              {queue.length === 0 ? (
                <div className="empty"><div className="empty-icon">✓</div><strong style={{ color:'#334155', marginBottom:'5px' }}>No active scans</strong><span style={{ fontSize:'13px' }}>New patient submissions will appear here.</span></div>
              ) : (
                <div className="table-wrap">
                  <table className="table"><thead><tr><th>Patient</th><th>Video</th><th>Status</th><th>Progress</th><th>Submitted</th><th></th></tr></thead><tbody>
                    {queue.map(scan => (
                      <tr key={scan.id}>
                        <td><strong style={{ fontFamily:'ui-monospace, SFMono-Regular, monospace', color:'#334155' }}>{scan.patient_id?.slice(0,8)}…</strong></td>
                        <td>{scan.video_filename}</td>
                        <td><span className={`status status-${scan.status}`}>{scan.status}</span></td>
                        <td style={{ minWidth:'180px' }}>
                          {scan.status === 'processing' ? (
                            <>
                              <div style={{ fontSize:'12px', color:'#475569', marginBottom:'6px' }}>
                                {scan.current_step_name ? `Step ${scan.current_step}/7 · ${scan.current_step_name}` : 'Starting…'}
                              </div>
                              <div className="progress-bar">
                                <div style={{ width:`${scan.progress_percent || 0}%`, transition:'width .5s ease' }} />
                              </div>
                            </>
                          ) : '—'}
                        </td>
                        <td className="muted">{scan.created_at ? new Date(scan.created_at).toLocaleString() : '—'}</td>
                        <td>{scan.status === 'rendered' ? <Link href={`/viewer/${scan.id}`} className="btn btn-secondary" style={{ minHeight:'34px', padding:'6px 10px' }}>Review</Link> : ''}</td>
                      </tr>
                    ))}
                  </tbody></table>
                </div>
              )}
            </div>
          )}

          {tab === 'patients' && (
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Patient records</h2>
                <input className="input" style={{ maxWidth:'260px' }} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search name or code" />
              </div>
              {filteredPatients.length === 0 ? (
                <div className="empty"><div className="empty-icon">⌕</div><strong style={{ color:'#334155', marginBottom:'5px' }}>{query ? 'No matching patients' : 'No patients registered'}</strong><span style={{ fontSize:'13px' }}>{query ? 'Try a different name or patient code.' : 'Register a patient to create a record.'}</span></div>
              ) : (
                <div className="table-wrap"><table className="table"><thead><tr><th>Patient</th><th>Code</th><th>Registered</th><th>Status</th><th></th></tr></thead><tbody>
                  {filteredPatients.map(p => (
                    <tr key={p.id}>
                      <td><div style={{ display:'flex', alignItems:'center', gap:'10px' }}><span className="record-avatar">{p.name?.slice(0,2).toUpperCase()}</span><strong>{p.name}</strong></div></td>
                      <td style={{ color:'#0F766E', fontWeight:750, fontFamily:'ui-monospace, monospace' }}>{p.patient_code}</td>
                      <td className="muted">{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                      <td><span className="status status-rendered">Active</span></td>
                      <td><button className="btn btn-secondary" style={{ minHeight:'34px', padding:'6px 10px' }}>Open record</button></td>
                    </tr>
                  ))}
                </tbody></table></div>
              )}
            </div>
          )}

          {tab === 'register' && (
            <div className="card" style={{ maxWidth:'720px' }}>
              <div className="card-header"><h2 className="card-title">Register a patient</h2></div>
              <div className="card-body">
                <div className="grid-2" style={{ marginBottom:'16px' }}>
                  <div className="field"><label className="label" htmlFor="patient-name">Full name</label><input id="patient-name" className="input" placeholder="e.g. Juan dela Cruz" value={newPatient.name} onChange={e => setNewPatient({ ...newPatient, name:e.target.value })} /></div>
                  <div className="field"><label className="label" htmlFor="patient-code">Patient code</label><input id="patient-code" className="input" placeholder="e.g. PT-002" value={newPatient.patient_code} onChange={e => setNewPatient({ ...newPatient, patient_code:e.target.value })} /></div>
                </div>
                <div className="notice notice-warning" style={{ marginBottom:'16px' }}>Only register a patient after confirming clinic consent and identity.</div>
                <button className="btn btn-primary" onClick={createPatient} disabled={!newPatient.name || !newPatient.patient_code}>Create patient record</button>
                {message && <div className="notice notice-success" style={{ marginTop:'12px' }}>{message}</div>}
              </div>
            </div>
          )}
        </div>
      </main>
    </>
  )
}

function Stat({ label, value, meta, tone }) {
  return <div className="metric-card"><div className="metric-head"><span>{label}</span><span className="metric-icon" style={{ color:tone, background:`${tone}12` }}>•</span></div><div className="metric-value" style={{ color:tone }}>{value}</div><div className="metric-meta">{meta}</div></div>
}
