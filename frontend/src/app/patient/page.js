'use client'
import { useState, useEffect, useRef } from 'react'
import Navbar from '../components/Navbar'

const STATUS_STYLE = {
  queued: { color: '#92400e', background: '#fef3c7' },
  processing: { color: '#1e40af', background: '#dbeafe' },
  rendered: { color: '#065f46', background: '#d1fae5' },
  failed: { color: '#991b1b', background: '#fee2e2' },
}

export default function PatientPage() {
  const [patientId, setPatientId] = useState('')
  const [patientCode, setPatientCode] = useState('')
  const [patientName, setPatientName] = useState('')
  const [scans, setScans] = useState([])
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')
  const [step, setStep] = useState('login') // login | portal
  const fileRef = useRef()

  const handleLogin = async () => {
    if (!patientCode) return
    try {
      const res = await fetch(`/api/patients/`)
      const patients = await res.json()
      const found = patients.find(p => p.patient_code === patientCode)
      if (found) {
        setPatientId(found.id)
        setPatientName(found.name)
        setStep('portal')
        loadScans(found.id)
      } else {
        setMessage('Patient code not found. Please contact your clinic.')
      }
    } catch {
      setMessage('Could not connect to server.')
    }
  }

  const loadScans = async (pid) => {
    try {
      const res = await fetch(`/api/scans/patient/${pid}`)
      const data = await res.json()
      setScans(data)
    } catch { }
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setMessage('')
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`http://localhost:8000/scans/upload/${patientId}`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (data.scan_id) {
        setMessage('Video uploaded successfully. Processing will begin shortly.')
        loadScans(patientId)
      }
    } catch {
      setMessage('Upload failed. Please try again.')
    }
    setUploading(false)
  }

  useEffect(() => {
    if (step === 'portal' && patientId) {
      const interval = setInterval(() => loadScans(patientId), 10000)
      return () => clearInterval(interval)
    }
  }, [step, patientId])

  if (step === 'login') return (
    <>
      <Navbar />
      <main style={{ maxWidth: '400px', margin: '6rem auto', padding: '0 1rem' }}>
        <div style={{ background: 'white', borderRadius: '12px', padding: '2rem', border: '1px solid #e5e7eb' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '0.5rem' }}>Patient Portal</h1>
          <p style={{ color: '#6b7280', marginBottom: '2rem', fontSize: '14px' }}>Enter your patient code to access your wound scans.</p>
          <input
            type="text"
            placeholder="Patient code (e.g. PT-001)"
            value={patientCode}
            onChange={e => setPatientCode(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #d1d5db', marginBottom: '1rem', fontSize: '14px' }}
          />
          <button onClick={handleLogin} style={{
            width: '100%', background: '#0F6E56', color: 'white',
            padding: '10px', borderRadius: '8px', border: 'none',
            fontWeight: 600, cursor: 'pointer', fontSize: '14px'
          }}>
            Access my scans
          </button>
          {message && <p style={{ marginTop: '1rem', color: '#991b1b', fontSize: '13px' }}>{message}</p>}
        </div>
      </main>
    </>
  )

  return (
    <>
      <Navbar />
      <main style={{ maxWidth: '760px', margin: '0 auto', padding: '2rem 1rem' }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 700 }}>Welcome, {patientName}</h1>
          <p style={{ color: '#6b7280', fontSize: '14px' }}>Patient code: {patientCode}</p>
        </div>

        <div style={{ background: 'white', borderRadius: '12px', padding: '2rem', border: '1px solid #e5e7eb', marginBottom: '2rem' }}>
          <h2 style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Upload Smartphone Video</h2>
          <p style={{ color: '#6b7280', fontSize: '14px', marginBottom: '1.5rem' }}>
            Capture a steady 360-degree sweep around the wound. No depth sensor required.
          </p>
          <div
            onClick={() => fileRef.current.click()}
            style={{
              border: '2px dashed #d1d5db', borderRadius: '8px',
              padding: '3rem', textAlign: 'center', cursor: 'pointer',
              background: '#f9fafb'
            }}
          >
            <div style={{ fontSize: '32px', marginBottom: '0.5rem' }}>☁️</div>
            <p style={{ fontWeight: 500, marginBottom: '0.25rem' }}>Click to browse or drag and drop</p>
            <p style={{ color: '#9ca3af', fontSize: '13px' }}>MP4, MOV up to 100MB</p>
            <input ref={fileRef} type="file" accept="video/*" onChange={handleUpload} style={{ display: 'none' }} />
          </div>
          {uploading && <p style={{ marginTop: '1rem', color: '#1e40af', fontSize: '14px' }}>Uploading...</p>}
          {message && <p style={{ marginTop: '1rem', color: '#065f46', fontSize: '14px' }}>{message}</p>}
        </div>

        <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
          <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid #e5e7eb' }}>
            <h2 style={{ fontWeight: 600 }}>Your 3D Scans</h2>
          </div>
          {scans.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: '#9ca3af' }}>
              No scans yet. Upload a video to get started.
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: '12px', color: '#6b7280', fontWeight: 600 }}>FILE</th>
                  <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: '12px', color: '#6b7280', fontWeight: 600 }}>STATUS</th>
                  <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: '12px', color: '#6b7280', fontWeight: 600 }}>DATE</th>
                  <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: '12px', color: '#6b7280', fontWeight: 600 }}>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((scan, i) => (
                  <tr key={scan.id} style={{ borderTop: i > 0 ? '1px solid #f3f4f6' : 'none' }}>
                    <td style={{ padding: '12px 16px', fontSize: '14px' }}>{scan.video_filename}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        ...STATUS_STYLE[scan.status],
                        padding: '2px 10px', borderRadius: '999px', fontSize: '12px', fontWeight: 500
                      }}>
                        {scan.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>
                      {new Date(scan.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {scan.status === 'rendered' && (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <a href={`/viewer/${scan.id}`} style={{ color: '#0F6E56', fontSize: '13px', fontWeight: 500 }}>
                            View 3D
                          </a>
                          <span style={{ color: '#d1d5db' }}>|</span>
                          <a href={`/api/reports/${scan.id}/pdf`} style={{ color: '#6b7280', fontSize: '13px' }}>
                            PDF
                          </a>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </>
  )
}
