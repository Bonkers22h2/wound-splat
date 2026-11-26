export type CalibrationStatus = 'calibrated' | 'uncalibrated'
export type AlignmentStatus = 'aligned' | 'caveat' | 'poor'

export interface WoundMeasurements {
  surface_area_cm2: number
  volume_cm3: number
  max_depth_mm: number
  width_cm: number
  height_cm: number
}

export interface TissueComposition {
  granulation_percent: number
  fibrin_percent: number
  callus_percent: number
  wound_fraction_of_box: number
}

export interface WoundScan {
  id: string
  scanNumber: number
  label: string
  visitOffset: string
  date: string
  time: string
  frameCount: number
  registrationRate: number
  calibrationStatus: CalibrationStatus
  alignmentStatus: AlignmentStatus
  measurements: WoundMeasurements
  tissue: TissueComposition | null
}

export const LONGITUDINAL_SCANS: WoundScan[] = [
  {
    id: 'WS-001',
    scanNumber: 1,
    label: 'Baseline',
    visitOffset: 'Visit 1',
    date: 'Oct 14, 2026',
    time: '09:12 AM',
    frameCount: 68,
    registrationRate: 88,
    calibrationStatus: 'calibrated',
    alignmentStatus: 'aligned',
    measurements: {
      surface_area_cm2: 14.82,
      volume_cm3: 6.48,
      max_depth_mm: 7.1,
      width_cm: 4.6,
      height_cm: 4.1,
    },
    tissue: {
      granulation_percent: 38,
      fibrin_percent: 42,
      callus_percent: 20,
      wound_fraction_of_box: 24,
    },
  },
  {
    id: 'WS-002',
    scanNumber: 2,
    label: '+7 Days',
    visitOffset: 'Visit 2',
    date: 'Oct 21, 2026',
    time: '10:24 AM',
    frameCount: 74,
    registrationRate: 93,
    calibrationStatus: 'calibrated',
    alignmentStatus: 'aligned',
    measurements: {
      surface_area_cm2: 13.64,
      volume_cm3: 5.71,
      max_depth_mm: 6.6,
      width_cm: 4.4,
      height_cm: 3.9,
    },
    tissue: {
      granulation_percent: 49,
      fibrin_percent: 34,
      callus_percent: 17,
      wound_fraction_of_box: 21,
    },
  },
  {
    id: 'WS-003',
    scanNumber: 3,
    label: '+14 Days',
    visitOffset: 'Visit 3',
    date: 'Oct 28, 2026',
    time: '08:51 AM',
    frameCount: 82,
    registrationRate: 91,
    calibrationStatus: 'uncalibrated',
    alignmentStatus: 'caveat',
    measurements: {
      surface_area_cm2: 12.18,
      volume_cm3: 4.92,
      max_depth_mm: 5.9,
      width_cm: 4.1,
      height_cm: 3.7,
    },
    tissue: null,
  },
]
