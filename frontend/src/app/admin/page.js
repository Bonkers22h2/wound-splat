'use client'
import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'

const STATUS_STYLE = {
  queued:     { color: '#92400e', background: '#fef3c7' },
  processing: { color: '#1e40af', background: '#dbeafe' },
  rendered:   { color: '#065f46', background: '#d1fae5' },
  failed:     { color: '#991b1b', background: '#fee2e2' },
}

export default function AdminPage() {
  const [queue, setQueue] = useState([])
  const [patients, setPatients] = useState([])
  const [newPatient, setNewPatient] = useState({ name: '', patient_code: '' })
  const [message, setMessage] = useState('')
  const [tab, setTab] = useState('queue')

  const loadQueue = async () => {
    try {
      const res = await fetch('/api/scans/admin/queue')
      const data = await res.json()
      setQueue(data)
    } catch {}
  }

  const loadPatients = async () => {
    try {
      const res = await fetch('/api/patients/')
      const data = await res.json()
      setPatients(data)
    } catch {}
  }

  const createPatient = async () => {
    if (!newPatient.name || !newPatient.patient_code) return
    try {
      const res = await fetch('/api/patients/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPatient)
      })
      if (res.ok) {
        setMessage(`Patient ${newPatient.patient_code} created successfully.`)
        setNewPatient({ name: '', patient_code: '' })
        loadPatients()
      } else {
        const err = await res.json()
        setMessage(err.detail || 'Error creating patient.')
      }
    } catch {
      setMessage('Could not connect to server.')
    }
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

  return (
    <>
      <Navbar />
      <main style={{ maxWidth: '960px', margin: '0 auto', padding: '2rem 1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <div>
            <h1 style={{ fontSize: '24px', fontWeight: 700 }}>Clinical Admin</h1>
            <p style={{ color: '#6b7280', fontSize: '14px' }}>Wound-Splat processing dashboard</p>
          </div>
          <div style={{ background: '#d1fae5', color: '#065f46', padding: '6px 14px', borderRadius: '999px', fontSize: '13px', fontWeight: 600 }}>
            GPU: NVIDIA RTX 4050 Active
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
          {[
            { label: 'Processing', value: processing, color: '#1e40af', bg: '#dbeafe' },
            { label: 'Queued', value: queued, color: '#92400e', bg: '#fef3c7' },
            { label: 'Completed', value: rendered, color: '#065f46', bg: '#d1fae5' },
          ].map((stat, i) => (
            <div key={i} style={{ background: 'white', borderRadius: '12px', padding: '1.25rem', border: '1px solid #e5e7eb' }}>
              <p style={{ fontSize: '13px', color: '#6b7280', marginBottom: '0.5rem' }}>{stat.label}</p>
              <p style={{ fontSize: '32px', fontWeight: 700, color: stat.color }}>{stat.value}</p>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem' }}>
          {['queue', 'patients'].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '8px 20px', borderRadius: '8px', border: 'none', cursor: 'pointer',
              background: tab === t ? '#0F6E56' : 'white',
              color: tab === t ? 'white' : '#374151',
              fontWeight: 500, fontSize: '14px',
              border: tab === t ? 'none' : '1px solid #e5e7eb'
            }}>
              {t === 'queue' ? 'Processing Queue' : 'Patients'}
            </button>
          ))}
        </div>

        {tab === 'queue' && (
          <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
            <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontWeight: 600 }}>Processing Queue</h2>
              <button onClick={loadQueue} style={{ fontSize: '13px', color: '#0F6E56', background: 'none', border: 'none', cursor: 'pointer' }}>Refresh</button>
            </div>
            {queue.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: '#9ca3af' }}>No scans in queue.</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f9fafb' }}>
                    {['Patient ID', 'Video', 'Status', 'Progress', 'Submitted', 'Completed'].map(h => (
                      <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: '12px', color: '#6b7280', fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {queue.map((scan, i) => (
                    <tr key={scan.id} style={{ borderTop: i > 0 ? '1px solid #f3f4f6' : 'none' }}>
                      <td style={{ padding: '12px 16px', fontSize: '13px', fontFamily: 'monospace' }}>{scan.patient_id.slice(0, 8)}...</td>
                      <td style={{ padding: '12px 16px', fontSize: '13px' }}>{scan.video_filename}</td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{
                          ...STATUS_STYLE[scan.status],
                          padding: '2px 10px', borderRadius: '999px', fontSize: '12px', fontWeight: 500
                        }}>
                          {scan.status}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '13px', minWidth: '180px' }}>
                        {scan.status === 'processing' ? (
                          <div>
                            <div style={{ fontSize: '12px', color: '#374151', marginBottom: '4px' }}>
                              {scan.current_step_name
                                ? `Step ${scan.current_step}/7: ${scan.current_step_name}`
                                : 'Starting...'}
                              {scan.current_step === 3 && scan.progress_percent > 0
                                ? ` (${Math.round(scan.progress_percent)}%)`
                                : ''}
                            </div>
                            <div style={{ width: '100%', height: '6px', background: '#e5e7eb', borderRadius: '999px', overflow: 'hidden' }}>
                              <div style={{
                                height: '100%',
                                borderRadius: '999px',
                                background: '#1e40af',
                                width: scan.current_step
                                  ? `${(((scan.current_step - 1) + (scan.progress_percent || 0) / 100) / 7) * 100}%`
                                  : '0%',
                                transition: 'width 0.5s ease'
                              }} />
                            </div>
                          </div>
                        ) : (
                          <span style={{ color: '#9ca3af' }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>
                        {new Date(scan.created_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>
                        {scan.completed_at ? new Date(scan.completed_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {tab === 'patients' && (
          <div style={{ display: 'grid', gap: '1.5rem' }}>
            <div style={{ background: 'white', borderRadius: '12px', padding: '1.5rem', border: '1px solid #e5e7eb' }}>
              <h2 style={{ fontWeight: 600, marginBottom: '1rem' }}>Add Patient</h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '1rem', alignItems: 'end' }}>
                <div>
                  <label style={{ fontSize: '13px', color: '#374151', display: 'block', marginBottom: '4px' }}>Full name</label>
                  <input
                    type="text"
                    placeholder="e.g. Juan dela Cruz"
                    value={newPatient.name}
                    onChange={e => setNewPatient({ ...newPatient, name: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '14px' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '13px', color: '#374151', display: 'block', marginBottom: '4px' }}>Patient code</label>
                  <input
                    type="text"
                    placeholder="e.g. PT-002"
                    value={newPatient.patient_code}
                    onChange={e => setNewPatient({ ...newPatient, patient_code: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '14px' }}
                  />
                </div>
                <button onClick={createPatient} style={{
                  background: '#0F6E56', color: 'white', padding: '8px 20px',
                  borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '14px'
                }}>
                  Add
                </button>
              </div>
              {message && <p style={{ marginTop: '1rem', fontSize: '13px', color: '#065f46' }}>{message}</p>}
            </div>

            <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
              <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid #e5e7eb' }}>
                <h2 style={{ fontWeight: 600 }}>All Patients</h2>
              </div>
              {patients.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: '#9ca3af' }}>No patients registered yet.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f9fafb' }}>
                      {['Name', 'Patient Code', 'Registered'].map(h => (
                        <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: '12px', color: '#6b7280', fontWeight: 600 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {patients.map((p, i) => (
                      <tr key={p.id} style={{ borderTop: i > 0 ? '1px solid #f3f4f6' : 'none' }}>
                        <td style={{ padding: '12px 16px', fontSize: '14px', fontWeight: 500 }}>{p.name}</td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', fontFamily: 'monospace', color: '#0F6E56' }}>{p.patient_code}</td>
                        <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>{new Date(p.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </main>
    </>
  )
}