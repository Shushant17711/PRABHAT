import React from 'react'
import { VERDICT } from '../api.js'

/* DESIGN §5-S7 dashboard item 3.
   "The gate panel — SFS score, cross-scale IoU, verdict, reason. Prominent.
    This is the thing to point at during the demo."

   It is the hero of this layout for a reason: the claim the project rests on
   is that a generative system can refuse to speak. That refusal has to be
   visible, and it has to say why. */

function Metric({ name, value, threshold, thresholdLabel, format, pass, hint }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  const color = pass ? 'var(--good)' : 'var(--critical)'
  return (
    <div className="metric">
      <div className="metric-top">
        <span className="metric-name">{name}</span>
        <span className="metric-val mono" style={{ color }}>
          {format(value)}
        </span>
      </div>
      <div className="bar">
        <div className="bar-fill" style={{ width: `${pct}%`, '--bar-color': color }} />
        {threshold != null && (
          <div
            className="bar-thresh"
            style={{ left: `${threshold * 100}%` }}
            data-label={thresholdLabel}
          />
        )}
      </div>
      <div className="metric-foot">
        <span>{hint}</span>
        <span>{pass ? 'PASS' : 'FAIL'}</span>
      </div>
    </div>
  )
}

export default function GatePanel({ gate, isStub }) {
  if (!gate) return null
  const v = VERDICT[gate.verdict] ?? VERDICT.PASS

  return (
    <section
      className="panel gate rise rise-1"
      style={{ '--verdict-color': v.color }}
      aria-label="Runtime safety gates"
    >
      <div className="panel-head">
        <span className="label">S5 · runtime gates</span>
        {isStub && (
          <span className="badge badge-stub">
            <span className="badge-dot" /> stub
          </span>
        )}
      </div>

      <div className="panel-body">
        <p className="verdict">{gate.verdict}</p>
        <p className="verdict-sub">
          <span className="verdict-icon" aria-hidden="true">{v.icon}</span>
          {v.label}
        </p>

        <p className="reason">{gate.reason}</p>

        <Metric
          name="G1 · spectral fidelity"
          value={gate.spectral_fidelity}
          threshold={0.7}
          thresholdLabel="0.70"
          format={(x) => x.toFixed(2)}
          pass={gate.spectral_pass}
          hint="penalises smoothing"
        />

        <Metric
          name="G2 · cross-scale IoU"
          value={gate.cross_scale_iou}
          threshold={0.4}
          thresholdLabel="0.40"
          format={(x) => x.toFixed(2)}
          pass={gate.cross_scale_pass}
          hint={`centroid ${gate.cross_scale_centroid_km.toFixed(0)} km · limit 50 km`}
        />
      </div>
    </section>
  )
}
