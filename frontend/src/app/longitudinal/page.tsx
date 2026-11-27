'use client'

import { useMemo, useState } from 'react'
import Navbar from '../components/Navbar'
import {
  LONGITUDINAL_SCANS,
  type WoundMeasurements,
  type WoundScan,
} from '@/lib/longitudinalFixtures'

type ViewMode = 'side' | 'overlay' | '3d'

const measurementRows: Array<{
  key: keyof WoundMeasurements
  label: string
  unit: string
}> = [
  { key: 'surface_area_cm2', label: 'Planar Surface Area', unit: 'cm²' },
  { key: 'volume_cm3', label: 'Cavity Volume', unit: 'cm³' },
  { key: 'max_depth_mm', label: 'Max Depth', unit: 'mm' },
  { key: 'width_cm', label: 'Width', unit: 'cm' },
  { key: 'height_cm', label: 'Height', unit: 'cm' },
]

export default function LongitudinalPage() {
  const [scanAId, setScanAId] = useState('WS-002')
  const [scanBId, setScanBId] = useState('WS-003')
  const [viewMode, setViewMode] = useState<ViewMode>('side')
  const [overlay, setOverlay] = useState(52)
  const [exported, setExported] = useState(false)

  const scanA = LONGITUDINAL_SCANS.find(scan => scan.id === scanAId)!
  const scanB = LONGITUDINAL_SCANS.find(scan => scan.id === scanBId)!
  const warning = useMemo(
    () => scanA.calibrationStatus !== 'calibrated'
      || scanB.calibrationStatus !== 'calibrated'
      || scanA.alignmentStatus !== 'aligned'
      || scanB.alignmentStatus !== 'aligned',
    [scanA, scanB],
  )

  return (
    <>
      <Navbar />
      <main className="longitudinal-page">
        <div className="longitudinal-container">
          <header className="long-header">
            <div>
              <div className="long-eyebrow">Longitudinal wound monitoring</div>
              <h1>Scan comparison</h1>
            </div>
            <div className="patient-chip">
              <span className="patient-avatar">MS</span>
              <div>
                <strong>Maria Santos</strong>
                <span>PT-001 · Left plantar ulcer</span>
              </div>
            </div>
          </header>

          <Timeline
            scanAId={scanAId}
            scanBId={scanBId}
            onScanAChange={setScanAId}
            onScanBChange={setScanBId}
          />

          {warning && (
            <div className="comparison-warning">
              <span className="warning-symbol">!</span>
              <div>
                <strong>Interpret apparent changes with caution</strong>
                <p>
                  One or more selected scans has an uncalibrated scale or alignment caveat.
                  Lighting, camera angle, scale, and registration noise may affect visual and geometric changes.
                </p>
              </div>
            </div>
          )}

          <section className="comparison-card">
            <div className="comparison-toolbar">
              <div className="view-tabs" role="tablist" aria-label="Comparison view">
                {([
                  ['side', 'Side-by-Side Viewports'],
                  ['overlay', 'Overlay / Opacity'],
                  ['3d', '3D / Tissue Preview'],
                ] as Array<[ViewMode, string]>).map(([mode, label]) => (
                  <button
                    key={mode}
                    className={viewMode === mode ? 'active' : ''}
                    onClick={() => setViewMode(mode)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {viewMode === 'side' && (
                <div className="toolbar-status">
                  <span className="status-dot" /> Aligned preview
                </div>
              )}
            </div>
            <ComparisonStage
              scanA={scanA}
              scanB={scanB}
              viewMode={viewMode}
              overlay={overlay}
              setOverlay={setOverlay}
            />
          </section>

          <div className="analysis-grid">
            <section className="analysis-card">
              <div className="analysis-header">
                <div>
                  <span className="section-kicker">Geometric comparison</span>
                  <h2>Measurement deltas</h2>
                </div>
                <span className="decision-badge">Decision support</span>
              </div>
              <MeasurementTable scanA={scanA} scanB={scanB} />
            </section>

            <section className="analysis-card trend-card">
              <div className="analysis-header">
                <div>
                  <span className="section-kicker">Multi-visit trend</span>
                  <h2>Volume & depth</h2>
                </div>
              </div>
              <TrendChart />
            </section>
          </div>

          <section className="analysis-card tissue-card">
            <div className="analysis-header">
              <div>
                <span className="section-kicker">Tissue segmentation</span>
                <h2>Tissue composition</h2>
              </div>
              <div className="legend">
                <span><i style={{ background: '#10B981' }} />Granulation</span>
                <span><i style={{ background: '#F59E0B' }} />Fibrin</span>
                <span><i style={{ background: '#3B82F6' }} />Callus</span>
              </div>
            </div>
            <TissueComparison scanA={scanA} scanB={scanB} />
          </section>

          <footer className="clinical-footer">
            <div className="disclaimer">
              <strong>Clinical decision-support prototype</strong>
              <p>
                Automated measurements and tissue breakdowns are not a diagnosis or guaranteed biological healing claim.
                RGB video does not capture perfusion, infection, warmth, or palpation findings. Confirm interpretations
                with clinical assessment and established wound-care protocols.
              </p>
            </div>
            <button
              className="export-button"
              onClick={() => {
                setExported(true)
                window.setTimeout(() => setExported(false), 2400)
              }}
            >
              {exported ? 'Summary prepared' : 'Export Comparison Summary'}
              <span>{exported ? '✓' : 'UI Preview'}</span>
            </button>
          </footer>
        </div>
      </main>
    </>
  )
}

function Timeline({
  scanAId,
  scanBId,
  onScanAChange,
  onScanBChange,
}: {
  scanAId: string
  scanBId: string
  onScanAChange: (id: string) => void
  onScanBChange: (id: string) => void
}) {
  return (
    <section className="timeline-bar">
      <div className="timeline-track">
        {LONGITUDINAL_SCANS.map((scan, index) => (
          <div className="timeline-stop" key={scan.id}>
            {index > 0 && <div className="timeline-line" />}
            <button
              className={scanAId === scan.id || scanBId === scan.id ? 'timeline-node selected' : 'timeline-node'}
              onClick={() => onScanBChange(scan.id)}
              title={`Set ${scan.visitOffset} as comparison scan`}
            >
              <span className="timeline-number">{scan.scanNumber}</span>
            </button>
            <div className="timeline-meta">
              <strong>{scan.visitOffset} · {scan.label}</strong>
              <span>{scan.date} · {scan.frameCount} frames</span>
              <div>
                <span className={`mini-status ${scan.calibrationStatus}`}>
                  {scan.calibrationStatus === 'calibrated' ? 'Calibrated' : 'Uncalibrated'}
                </span>
                <span className="rate">{scan.registrationRate}% aligned</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="scan-selectors">
        <label>
          <span>Baseline / Previous Scan</span>
          <select value={scanAId} onChange={event => onScanAChange(event.target.value)}>
            {LONGITUDINAL_SCANS.map(scan => (
              <option key={scan.id} value={scan.id}>
                Scan #{scan.scanNumber} · {scan.visitOffset}
              </option>
            ))}
          </select>
        </label>
        <button className="swap-button" type="button" aria-label="Swap selected scans"
          onClick={() => {
            const currentA = scanAId
            onScanAChange(scanBId)
            onScanBChange(currentA)
          }}>⇄</button>
        <label>
          <span>Current / Comparison Scan</span>
          <select value={scanBId} onChange={event => onScanBChange(event.target.value)}>
            {LONGITUDINAL_SCANS.map(scan => (
              <option key={scan.id} value={scan.id}>
                Scan #{scan.scanNumber} · {scan.visitOffset}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  )
}

function WoundPreview({ scan, translucent = false }: { scan: WoundScan; translucent?: boolean }) {
  return (
    <div className={translucent ? 'wound-preview translucent' : 'wound-preview'} aria-label={`Mock wound preview for ${scan.visitOffset}`}>
      <div className="reference-grid" />
      <svg viewBox="0 0 300 220" role="img" aria-label="Mock 3D wound reconstruction">
        <defs>
          <radialGradient id={`depth-${scan.id}`} cx="48%" cy="45%">
            <stop offset="0%" stopColor="#0F172A" />
            <stop offset="44%" stopColor="#087F74" />
            <stop offset="72%" stopColor="#10B981" />
            <stop offset="100%" stopColor="#C7F9EC" />
          </radialGradient>
          <filter id={`shadow-${scan.id}`}>
            <feGaussianBlur stdDeviation="7" />
          </filter>
        </defs>
        <ellipse cx="150" cy="172" rx="92" ry="18" fill="#020617" opacity=".7" filter={`url(#shadow-${scan.id})`} />
        <path d="M52 123 C55 82 88 58 126 64 C156 69 169 48 206 65 C242 82 260 124 238 151 C216 178 184 171 158 188 C124 210 78 181 67 151 Z"
          fill="#E2E8F0" opacity=".88" />
        <path d="M70 124 C72 94 96 76 126 81 C152 85 166 66 197 79 C225 91 239 123 220 145 C203 164 178 155 155 174 C127 196 91 169 82 147 Z"
          fill={`url(#depth-${scan.id})`} />
        <path d="M94 123 C97 102 115 92 134 96 C151 100 160 88 183 97 C203 105 210 126 197 141 C181 159 162 148 145 160 C123 176 102 151 96 139 Z"
          fill="#0F766E" opacity=".98" />
        <path d="M116 124 C119 111 130 106 143 110 C154 113 169 107 180 115 C189 123 186 137 177 145 C164 156 151 145 140 151 C126 158 115 143 116 124 Z"
          fill="#0F172A" />
      </svg>
    </div>
  )
}

function ComparisonStage({
  scanA,
  scanB,
  viewMode,
  overlay,
  setOverlay,
}: {
  scanA: WoundScan
  scanB: WoundScan
  viewMode: ViewMode
  overlay: number
  setOverlay: (value: number) => void
}) {
  const [rotation, setRotation] = useState('0°')

  if (viewMode === 'overlay') {
    return (
      <div className="stage-overlay">
        <div className="overlay-base"><WoundPreview scan={scanA} /></div>
        <div className="overlay-current" style={{ clipPath: `inset(0 ${100 - overlay}% 0 0)` }}>
          <WoundPreview scan={scanB} translucent />
        </div>
        <div className="overlay-scan-label left">{scanA.visitOffset}</div>
        <div className="overlay-scan-label right">{scanB.visitOffset}</div>
        <div className="opacity-control">
          <span>{scanA.visitOffset}</span>
          <input
            aria-label="Overlay opacity"
            type="range"
            min="0"
            max="100"
            value={overlay}
            onChange={event => setOverlay(Number(event.target.value))}
          />
          <span>{scanB.visitOffset}</span>
        </div>
      </div>
    )
  }

  if (viewMode === '3d') {
    return (
      <div className="stage-3d">
        <div className="stage-preview-large" style={{ transform: `scale(.96) rotate(${rotation})` }}>
          <WoundPreview scan={scanB} />
          <div className="tissue-overlay granulation" />
          <div className="tissue-overlay fibrin" />
        </div>
        <div className="orientation-controls">
          <span>Mock orientation</span>
          <button onClick={() => setRotation('-6deg')}>X −</button>
          <button onClick={() => setRotation('6deg')}>X +</button>
          <button onClick={() => setRotation('Y 6deg')}>Y +</button>
          <button onClick={() => setRotation('Z 5deg')}>Z +</button>
          <button onClick={() => setRotation('0deg')}>Reset View</button>
        </div>
        <div className="mock-note">
          Live interactive 3D registration/alignment is a mock UI preview.
          <span>{scanB.frameCount} frames · {scanB.registrationRate}% registration</span>
        </div>
      </div>
    )
  }

  return (
    <div className="side-stage">
      {[scanA, scanB].map((scan, index) => (
        <div className="viewport" key={scan.id}>
          <div className="viewport-label">
            <div>
              <strong>{index === 0 ? 'Scan A' : 'Scan B'} · {scan.visitOffset}</strong>
              <span>{scan.date} · {scan.time}</span>
            </div>
            <span className={`viewport-status ${scan.calibrationStatus}`}>
              {scan.calibrationStatus === 'calibrated' ? 'Calibrated' : 'Uncalibrated'}
            </span>
          </div>
          <WoundPreview scan={scan} />
        </div>
      ))}
      <div className="side-divider" />
    </div>
  )
}

function MeasurementTable({ scanA, scanB }: { scanA: WoundScan; scanB: WoundScan }) {
  return (
    <div className="measurement-table">
      <div className="measurement-row measurement-head">
        <span>Metric</span>
        <span>Scan A</span>
        <span>Scan B</span>
        <span>Apparent change</span>
      </div>
      {measurementRows.map(row => {
        const a = scanA.measurements[row.key]
        const b = scanB.measurements[row.key]
        const absolute = b - a
        const percent = a === 0 ? 0 : (absolute / a) * 100
        const improvement = absolute < 0
        return (
          <div className="measurement-row" key={row.key}>
            <strong>{row.label}</strong>
            <span>{a.toFixed(row.unit === 'mm' ? 1 : 2)} <small>{row.unit}</small></span>
            <span>{b.toFixed(row.unit === 'mm' ? 1 : 2)} <small>{row.unit}</small></span>
            <div className="delta-values">
              <span className={improvement ? 'delta positive' : 'delta negative'}>
                {absolute > 0 ? '+' : ''}{absolute.toFixed(row.unit === 'mm' ? 1 : 2)} {row.unit}
              </span>
              <span className={improvement ? 'delta-percent positive' : 'delta-percent negative'}>
                {percent > 0 ? '+' : ''}{percent.toFixed(1)}%
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function TrendChart() {
  const pointsVolume = [48, 53, 58]
  const pointsDepth = [24, 30, 36]
  return (
    <div className="trend-chart">
      <div className="trend-summary">
        <div><i className="trend-dot volume" /><span>Volume</span><strong>4.92 cm³</strong></div>
        <div><i className="trend-dot depth" /><span>Max depth</span><strong>5.9 mm</strong></div>
      </div>
      <svg viewBox="0 0 430 180" role="img" aria-label="Volume and depth trend across three visits">
        {[30, 70, 110, 150].map(y => (
          <line key={y} x1="28" x2="410" y1={y} y2={y} stroke="#E2E8F0" strokeWidth="1" />
        ))}
        <polyline
          points={pointsVolume.map((y, i) => `${70 + i * 150},${y}`).join(' ')}
          fill="none"
          stroke="#0284C7"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <polyline
          points={pointsDepth.map((y, i) => `${70 + i * 150},${y}`).join(' ')}
          fill="none"
          stroke="#0F766E"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="6 5"
        />
        {pointsVolume.map((y, i) => (
          <circle key={`v${i}`} cx={70 + i * 150} cy={y} r="5" fill="#FFFFFF" stroke="#0284C7" strokeWidth="3" />
        ))}
        {pointsDepth.map((y, i) => (
          <circle key={`d${i}`} cx={70 + i * 150} cy={y} r="5" fill="#FFFFFF" stroke="#0F766E" strokeWidth="3" />
        ))}
        {['Visit 1', 'Visit 2', 'Visit 3'].map((label, i) => (
          <text key={label} x={70 + i * 150} y="174" textAnchor="middle" fill="#94A3B8" fontSize="11">
            {label}
          </text>
        ))}
      </svg>
    </div>
  )
}

function TissueComparison({ scanA, scanB }: { scanA: WoundScan; scanB: WoundScan }) {
  const tissues = [
    { key: 'granulation_percent', label: 'Granulation', color: '#10B981' },
    { key: 'fibrin_percent', label: 'Fibrin', color: '#F59E0B' },
    { key: 'callus_percent', label: 'Callus', color: '#3B82F6' },
  ] as const

  return (
    <div className="tissue-comparison">
      {[scanA, scanB].map(scan => (
        <div className="tissue-column" key={scan.id}>
          <div className="tissue-column-title">
            <strong>{scan.visitOffset}</strong>
            <span>{scan.date}</span>
          </div>
          {scan.tissue ? (
            <>
              {tissues.map(tissue => (
                <div className="tissue-bar-row" key={tissue.key}>
                  <div className="tissue-bar-label">
                    <span>{tissue.label}</span>
                    <strong>{scan.tissue![tissue.key]}%</strong>
                  </div>
                  <div className="tissue-track">
                    <div style={{ width: `${scan.tissue![tissue.key]}%`, background: tissue.color }} />
                  </div>
                </div>
              ))}
              <div className="coverage">
                <span>Wound fraction of box</span>
                <strong>{scan.tissue.wound_fraction_of_box}%</strong>
              </div>
            </>
          ) : (
            <div className="tissue-empty">
              <span>—</span>
              <strong>Tissue analysis not available</strong>
              <p>Analysis has not run or wound pixels are below the detection threshold.</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
