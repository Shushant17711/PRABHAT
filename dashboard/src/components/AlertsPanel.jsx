import React from 'react'
import { SERIES, api } from '../api.js'

/* DESIGN §5-S7 dashboard item 6: a user-class selector that visibly changes
   which cells are alerted, driven by each class's p*. The rows below are the
   selector — clicking one filters the map to that class's alert. */

//: Exceedance field -> the words a responder actually reads.
const IMPACT = {
  p_rain_100mm_12h: 'driven by rainfall · >100 mm/12 h',
  p_wind_gt_62kt: 'driven by wind · >62 kt',
  p_t2m_gt_45c: 'driven by heat · >45 °C',
  p_t2m_lt_4c: 'driven by cold · <4 °C',
}

export default function AlertsPanel({ alerts, userClasses, selected, onSelect }) {
  const byClass = new Map(alerts.map((a) => [a.user_class, a]))

  return (
    <section className="panel rise rise-2" aria-label="Alerts by user class">
      <div className="panel-head">
        <span className="label">S6 · decisions</span>
        <span className="label">p &gt; p* = C/L</span>
      </div>

      {userClasses.map((uc) => {
        const a = byClass.get(uc.name)
        const isSel = selected === uc.name
        return (
          <div
            key={uc.name}
            className="alert-row"
            role="button"
            tabIndex={0}
            aria-selected={isSel}
            onClick={() => onSelect(isSel ? null : uc.name)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onSelect(isSel ? null : uc.name)
              }
            }}
          >
            <span className="alert-key" style={{ '--key': SERIES[uc.name] ?? 'var(--ink-faint)' }} />
            <div>
              <div className="alert-name">
                {uc.label || uc.name}
                {a && <span className={`sev sev-${a.severity}`}>{a.severity}</span>}
              </div>
              <div className="alert-meta">
                p* {uc.p_star.toFixed(3)} · band {uc.p_clear.toFixed(3)}–{uc.p_raise.toFixed(3)}
                {a ? ` · ${a.action}` : ' · no alert'}
              </div>
              {a?.impact_field && (
                /* "cyclone, 67%" is ambiguous between destructive wind and
                   destructive rainfall, and a responder stages different
                   equipment for each. */
                <div className="alert-impact">{IMPACT[a.impact_field] ?? a.impact_field}</div>
              )}
            </div>
            <div className="alert-p" style={{ color: a ? SERIES[uc.name] : 'var(--ink-faint)' }}>
              {a ? a.probability.toFixed(2) : '—'}
              <small>{a ? a.confidence_mode.toUpperCase() : 'BELOW P*'}</small>
            </div>
          </div>
        )
      })}

      {alerts.length > 0 && (
        <div style={{ padding: '10px 14px' }}>
          <a
            className="label"
            style={{ color: 'var(--series-1)', textDecoration: 'none' }}
            href={api.capUrl(alerts[0].alert_id)}
            target="_blank"
            rel="noreferrer"
          >
            ↗ CAP 1.2 XML
          </a>
        </div>
      )}
    </section>
  )
}
