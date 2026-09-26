import React from 'react'
import { SERIES } from '../api.js'

/* DESIGN §5-S6b / TASKS 13.3: "Report a churn metric on the dashboard: alert
   state changes per event. Show it with hysteresis on and off. The reduction
   is a headline number."

   It is also the direct answer to the problem statement's stated impact,
   "eliminating alert fatigue for the NDRF" — so it gets a real panel rather
   than a footnote. Paired bars per user class: notifications without the
   hysteresis band, and with it. */

export default function ChurnPanel({ churn }) {
  if (!churn || churn.length === 0) return null

  const max = Math.max(...churn.map((c) => c.churn_without), 1)
  const totalWithout = churn.reduce((s, c) => s + c.churn_without, 0)
  const totalWith = churn.reduce((s, c) => s + c.churn_with, 0)
  const overall = totalWithout ? (100 * (totalWithout - totalWith)) / totalWithout : 0
  const anyUnresolvable = churn.some((c) => c.band_resolvable === false)

  return (
    <section className="panel rise rise-4" aria-label="Alert churn">
      <div className="panel-head">
        <span className="label">S6b · alert churn</span>
        <span className="label" style={{ color: 'var(--good)' }}>
          −{overall.toFixed(0)}% overall
        </span>
      </div>

      <div className="panel-body">
        <p className="churn-intro">
          Notifications per event across the tube footprint, over{' '}
          <span className="mono">{churn[0].n_runs}</span> successive runs.
        </p>

        {churn.map((c) => {
          const wPct = (c.churn_without / max) * 100
          const hPct = (c.churn_with / max) * 100
          return (
            <div className="churn-row" key={c.user_class}>
              <div className="churn-top">
                <span className="churn-name">
                  <span className="churn-key" style={{ background: SERIES[c.user_class] }} />
                  {c.user_class.replace(/_/g, ' ')}
                </span>
                <span className="churn-delta mono">
                  {c.churn_without} → {c.churn_with}
                </span>
              </div>

              <div className="churn-bars">
                <div className="churn-bar">
                  <div className="churn-fill off" style={{ width: `${wPct}%` }} />
                  <span className="churn-tag">no band</span>
                </div>
                <div className="churn-bar">
                  <div
                    className="churn-fill on"
                    style={{ width: `${hPct}%`, background: SERIES[c.user_class] }}
                  />
                  <span className="churn-tag">hysteresis</span>
                </div>
              </div>

              <div className="churn-foot">
                <span>band {c.p_clear.toFixed(3)}–{c.p_raise.toFixed(3)}</span>
                <span style={{ color: c.lead_time_preserved ? 'var(--good)' : 'var(--critical)' }}>
                  {c.lead_time_preserved ? 'lead time kept' : 'LEAD TIME LOST'}
                </span>
              </div>
            </div>
          )
        })}

        {anyUnresolvable && (
          <p className="note">
            A band narrower than the ensemble's probability quantum (1/M) cannot be
            landed in, so hysteresis does less for those classes. Marked classes
            need a larger ensemble than the {churn[0].n_members} members simulated here.
          </p>
        )}
      </div>
    </section>
  )
}
