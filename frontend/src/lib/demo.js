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
