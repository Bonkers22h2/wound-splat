'use client'
import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import Navbar from '../components/Navbar'
import { Icon } from '../components/Icons'
import { patientApi, scanApi } from '@/lib/api'
import { DEMO_PATIENT, DEMO_SCANS } from '@/lib/demo'

const NO_REFERENCE = 'none'
const REFERENCE_OPTIONS = [
  { value: NO_REFERENCE, label: 'No reference — sizes unavailable' },
  { value: 'card', label: 'Bank / ID card' },
  { value: 'coin:us_quarter', label: 'US quarter' },
  { value: 'coin:us_nickel', label: 'US nickel' },
  { value: 'coin:us_penny', label: 'US penny' },
  { value: 'coin:us_dime', label: 'US dime' },
  { value: 'coin:eur_1', label: '1 euro coin' },
  { value: 'coin:eur_2', label: '2 euro coin' },
  { value: 'coin:gbp_1', label: 'UK £1 coin' },
  { value: 'coin:php_1', label: '₱1 peso' },
  { value: 'coin:php_5', label: '₱5 silver-colored coin' },
  { value: 'coin:php_5_bsp', label: 'Older ₱5 gold-colored coin' },
  { value: 'coin:php_10', label: '₱10 peso' },
]

export default function PatientPage() {
  const [patientId, setPatientId] = useState('')
  const [patientCode, setPatientCode] = useState('')
  const [patientName, setPatientName] = useState('')
  const [scans, setScans] = useState([])
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageIsError, setMessageIsError] = useState(false)
  const [step, setStep] = useState('login')
  const [referenceObject, setReferenceObject] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [tab, setTab] = useState('overview')
  const fileRef = useRef()

  const handleLogin = async () => {
    if (!patientCode.trim()) return
    if (patientCode.trim().toUpperCase() === DEMO_PATIENT.patient_code) {
      setPatientId(DEMO_PATIENT.id)
      setPatientName(DEMO_PATIENT.name)
      setScans(DEMO_SCANS)
      setStep('portal')
      setMessage('')
      return
    }
    try {
      const patients = await patientApi.list()
      const found = patients.find(p => p.patient_code === patientCode.trim())
      if (found) {
        setPatientId(found.id)
        setPatientName(found.name)
        setStep('portal')
        loadScans(found.id)
      } else {
        setMessage('Patient code not found. Please contact your clinic.')
      }
    } catch {
      setMessage('Could not connect to the server.')
    }
  }

  const loadScans = async (pid) => {
    try { setScans(await scanApi.listForPatient(pid)) } catch {}
  }

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0] || null)
    setMessage('')
  }

  const canSubmit = selectedFile && referenceObject && !uploading

  const handleSubmit = async () => {
    if (!canSubmit) return
    setUploading(true)
    setMessage('')
    try {
      const reference = referenceObject === NO_REFERENCE ? null : referenceObject
      const data = await scanApi.upload(patientId, selectedFile, reference)
      if (data.scan_id) {
        setMessageIsError(false)
        setMessage('Video uploaded successfully. Processing has started.')
        setSelectedFile(null)
        setReferenceObject('')
        if (fileRef.current) fileRef.current.value = ''
        loadScans(patientId)
      } else {
        setMessageIsError(true)
        setMessage(data.detail || 'Upload failed. Please try again.')
      }
    } catch {
      setMessageIsError(true)
      setMessage('Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  useEffect(() => {
    if (step !== 'portal' || !patientId) return
    const interval = setInterval(() => loadScans(patientId), 10000)
    return () => clearInterval(interval)
  }, [step, patientId])

  if (step === 'login') return (
    <>
      <Navbar />
      <main className="auth-shell">
        <section className="auth-panel">
          <div style={{ maxWidth:'420px', width:'100%', margin:'0 auto' }}>
            <div className="eyebrow">Patient access</div>
            <h1 style={{ fontSize:'32px', letterSpacing:'-.035em', marginBottom:'8px' }}>Welcome back</h1>
            <p className="helper" style={{ marginBottom:'28px' }}>Enter the patient code provided by your clinic.</p>
            <div className="field" style={{ marginBottom:'14px' }}>
              <label className="label" htmlFor="patient-code">Patient code</label>
              <input id="patient-code" className="input" value={patientCode} onChange={e => { setPatientCode(e.target.value); setMessage('') }}
                onKeyDown={e => e.key === 'Enter' && handleLogin()} placeholder="e.g. PT-001" />
            </div>
            <button className="btn btn-primary btn-block" onClick={handleLogin} disabled={!patientCode.trim()}>
              Access my scans
            </button>
            {message && <div className="notice notice-error" style={{ marginTop:'14px' }}>{message}</div>}
            <p className="helper" style={{ textAlign:'center', marginTop:'22px' }}>
              Need help? <span style={{ color:'#0F766E', fontWeight:700 }}>Contact your clinic</span>
            </p>
          </div>
        </section>
        <aside className="auth-aside">
          <div style={{ display:'flex', alignItems:'center', gap:'10px', fontWeight:750 }}>
            <span className="brand-mark"><Image src="/wound-splat-logo.png" alt="" fill sizes="38px" /></span> Wound-Splat
          </div>
          <div>
            <div style={{ fontSize:'12px', opacity:.72, marginBottom:'14px', textTransform:'uppercase', letterSpacing:'0.12em' }}>Your care timeline</div>
            <h2>Monitor healing with a clearer view.</h2>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'12px' }}>
            {['Upload','Process','Review'].map((item,i) => (
              <div key={item} style={{ borderTop:'1px solid rgba(255,255,255,.22)', paddingTop:'12px' }}>
                <div style={{ opacity:.6, fontSize:'11px' }}>0{i+1}</div><strong style={{ fontSize:'13px' }}>{item}</strong>
              </div>
            ))}
          </div>
        </aside>
      </main>
    </>
  )

  const latest = scans[0]
  return (
    <>
      <Navbar />
      <main className="page">
        <div className="page-container">
          <div className="page-header">
            <div>
              <div className="eyebrow">Patient portal</div>
              <h1 className="page-title">Good morning, {patientName}</h1>
              <p className="page-subtitle">Patient code · <strong style={{ color:'#334155' }}>{patientCode}</strong></p>
            </div>
            <button className="btn btn-primary" onClick={() => setTab('upload')}>Upload new scan</button>
          </div>

          <div className="tabs" style={{ marginBottom:'18px' }}>
            {[
              ['overview','Grid','Overview'],['history','Clock','History'],
              ['upload','Upload','Upload scan'],['profile','Patient','Profile'],
            ].map(([key,icon,label]) => (
              <button key={key} className={`tab ${tab === key ? 'active' : ''}`} onClick={() => setTab(key)} style={{ display:'flex', alignItems:'center', gap:'7px' }}>
                <Icon name={icon.toLowerCase()} size={15} />{label}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <>
              <div className="grid-3" style={{ marginBottom:'16px' }}>
                <div className="metric-card"><div className="metric-head"><span>Latest scan</span><span className="metric-icon"><Icon name="clock" size={16}/></span></div><div className="metric-value">{latest ? new Date(latest.created_at).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : '—'}</div><div className="metric-meta">{latest?.status || 'No scans yet'}</div></div>
                <div className="metric-card"><div className="metric-head"><span>Total scans</span><span className="metric-icon"><Icon name="activity" size={16}/></span></div><div className="metric-value">{scans.length}</div><div className="metric-meta">Longitudinal history</div></div>
                <div className="metric-card"><div className="metric-head"><span>Latest status</span><span className="metric-icon"><Icon name="eye" size={16}/></span></div><div style={{ marginTop:'11px' }}><span className={`status status-${latest?.status || 'queued'}`}>{latest?.status || 'Ready to begin'}</span></div><div className="metric-meta">Updated automatically</div></div>
              </div>
              <div className="card">
                <div className="card-header"><h2 className="card-title">Recent scans</h2><button className="tab" onClick={() => setTab('history')}>View history</button></div>
                <ScanTable scans={scans} />
              </div>
            </>
          )}

          {tab === 'history' && (
            <div className="card"><div className="card-header"><h2 className="card-title">Scan history</h2><span className="muted" style={{ fontSize:'12px' }}>{scans.length} scans</span></div><ScanTable scans={scans} /></div>
          )}

          {tab === 'upload' && (
            <div className="grid-2" style={{ alignItems:'start' }}>
              <div className="card">
                <div className="card-header"><h2 className="card-title">Upload a wound video</h2><span className="status status-warning">Size reference required</span></div>
                <div className="card-body">
                  <div className="field" style={{ marginBottom:'16px' }}>
                    <label className="label" htmlFor="reference">Size reference in the recording</label>
                    <select id="reference" className="select" value={referenceObject} onChange={e => setReferenceObject(e.target.value)}>
                      <option value="" disabled>Select the reference object</option>
                      {REFERENCE_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                    </select>
                  </div>
                  <div className="upload-panel" onClick={() => fileRef.current?.click()}>
                    <div className="upload-icon">{selectedFile ? '✓' : '＋'}</div>
                    <strong style={{ fontSize:'14px', marginBottom:'5px' }}>{selectedFile ? selectedFile.name : 'Choose a wound video'}</strong>
                    <span className="helper">{selectedFile ? `${(selectedFile.size/1024/1024).toFixed(1)} MB · Click to change` : 'MP4 or MOV · up to 100 MB'}</span>
                    <input ref={fileRef} type="file" accept="video/*" onChange={handleFileChange} style={{ display:'none' }} />
                  </div>
                  <button className="btn btn-primary btn-block" style={{ marginTop:'16px' }} onClick={handleSubmit} disabled={!canSubmit}>
                    {uploading ? 'Uploading…' : 'Submit scan'}
                  </button>
                  {message && <div className={`notice ${messageIsError?'notice-error':'notice-success'}`} style={{ marginTop:'12px' }}>{message}</div>}
                </div>
              </div>
              <div className="card">
                <div className="card-header"><h2 className="card-title">Before you record</h2></div>
                <div className="card-body">
                  {[
                    ['1','Set the reference','Place a matching coin or bank card flat next to the wound.'],
                    ['2','Improve visibility','Use bright, even lighting. Avoid glare and shadows.'],
                    ['3','Capture steadily','Move slowly around the wound, keeping it fully in frame.'],
                    ['4','Keep privacy in mind','Use the agreed recording location and approved device.'],
                  ].map(([n,title,text]) => (
                    <div key={n} style={{ display:'flex', gap:'12px', padding:'10px 0' }}>
                      <span style={{ width:'26px', height:'26px', flex:'0 0 26px', borderRadius:'50%', background:'#F0FDFA', color:'#0F766E', display:'grid', placeItems:'center', fontSize:'12px', fontWeight:800 }}>{n}</span>
                      <div><strong style={{ display:'block', fontSize:'13px', marginBottom:'3px' }}>{title}</strong><p className="helper">{text}</p></div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'profile' && (
            <div className="card" style={{ maxWidth:'720px' }}>
              <div className="card-header"><h2 className="card-title">Patient profile</h2></div>
              <div className="card-body grid-2">
                <div className="field"><label className="label">Name</label><input className="input" value={patientName} readOnly /></div>
                <div className="field"><label className="label">Patient code</label><input className="input" value={patientCode} readOnly /></div>
              </div>
            </div>
          )}
        </div>
      </main>
    </>
  )
}

function ScanTable({ scans }) {
  if (!scans.length) return <div className="empty"><div className="empty-icon">＋</div><strong style={{ color:'#334155', marginBottom:'5px' }}>No wound scans yet</strong><span style={{ fontSize:'13px' }}>Upload a video to begin your first scan.</span></div>
  return (
    <div className="table-wrap"><table className="table"><thead><tr><th>Video</th><th>Status</th><th>Date</th><th>Action</th></tr></thead><tbody>
      {scans.map(scan => (
        <tr key={scan.id}>
          <td><strong>{scan.video_filename}</strong></td>
          <td><span className={`status status-${scan.status}`}>{scan.status}</span></td>
          <td className="muted">{new Date(scan.created_at).toLocaleString()}</td>
          <td>{scan.status === 'rendered' ? <div style={{ display:'flex', gap:'12px' }}><Link href={`/viewer/${scan.id}`} style={{ color:'#0F766E', fontWeight:700, textDecoration:'none' }}>View 3D</Link><a href={`/api/reports/${scan.id}/pdf`} style={{ color:'#64748B', textDecoration:'none' }}>PDF</a></div> : '—'}</td>
        </tr>
      ))}
    </tbody></table></div>
  )
}
