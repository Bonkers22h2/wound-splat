export const DEMO_PATIENT = {
  id: 'demo-patient-001',
  name: 'Maria Santos',
  patient_code: 'PT-001',
  created_at: '2026-10-12T08:30:00Z',
}

export const DEMO_SCANS = [
  {
    id: 'demo-scan-001',
    patient_id: DEMO_PATIENT.id,
    video_filename: 'wound-video-nov-18.mp4',
    status: 'rendered',
    progress_percent: 100,
    current_step: 7,
    current_step_name: 'Complete',
    created_at: '2026-11-18T09:12:00Z',
    completed_at: '2026-11-18T09:29:00Z',
  },
  {
    id: 'demo-scan-002',
    patient_id: DEMO_PATIENT.id,
    video_filename: 'wound-video-nov-04.mp4',
    status: 'rendered',
    progress_percent: 100,
    current_step: 7,
    current_step_name: 'Complete',
    created_at: '2026-11-04T10:42:00Z',
    completed_at: '2026-11-04T10:58:00Z',
  },
]

export const DEMO_QUEUE = DEMO_SCANS.map((scan) => ({
  ...scan,
  patient_id: DEMO_PATIENT.id,
}))

export const DEMO_MEASUREMENTS = {
  scale_calibrated: true,
  surface_area_cm2: 18.42,
  volume_cm3: 7.68,
  max_depth_mm: 6.2,
  width_cm: 5.4,
  height_cm: 4.8,
  measurement_status: 'experimental',
  measurement_mode: 'surface',
  registration_rate: 91,
  frames_registered: 82,
  frames_extracted: 90,
}

export const DEMO_PATIENTS = [
  DEMO_PATIENT,
  {
    id: 'demo-patient-002',
    name: 'Juan dela Cruz',
    patient_code: 'PT-002',
    created_at: '2026-10-24T10:15:00Z',
  },
  {
    id: 'demo-patient-003',
    name: 'Liza Bautista',
    patient_code: 'PT-003',
    created_at: '2026-11-02T14:05:00Z',
  },
]

export const DEMO_ASSESSMENTS = [
  {
    ...DEMO_SCANS[0],
    patient_name: 'Maria Santos',
    patient_code: 'PT-001',
    scale_calibrated: true,
  },
  {
    id: 'demo-scan-003',
    patient_id: 'demo-patient-002',
    patient_name: 'Juan dela Cruz',
    patient_code: 'PT-002',
    video_filename: 'plantar-ulcer-nov-24.mp4',
    status: 'processing',
    progress_percent: 64,
    current_step: 4,
    current_step_name: 'Rendering views',
    created_at: '2026-11-24T08:40:00Z',
    registration_rate: 89,
    scale_calibrated: true,
  },
  {
    id: 'demo-scan-004',
    patient_id: 'demo-patient-003',
    patient_name: 'Liza Bautista',
    patient_code: 'PT-003',
    video_filename: 'heel-capture-nov-22.mov',
    status: 'queued',
    progress_percent: 0,
    current_step: 0,
    current_step_name: 'Queued',
    created_at: '2026-11-22T15:18:00Z',
    registration_rate: null,
    scale_calibrated: false,
  },
  {
    ...DEMO_SCANS[1],
    patient_name: 'Maria Santos',
    patient_code: 'PT-001',
    scale_calibrated: true,
  },
  {
    id: 'demo-scan-005',
    patient_id: 'demo-patient-002',
    patient_name: 'Juan dela Cruz',
    patient_code: 'PT-002',
    video_filename: 'foot-lateral-nov-01.mp4',
    status: 'failed',
    progress_percent: 28,
    current_step: 2,
    current_step_name: 'COLMAP alignment',
    created_at: '2026-11-01T11:05:00Z',
    registration_rate: 31,
    scale_calibrated: false,
  },
]
