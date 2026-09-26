import React from 'react'

/* DESIGN §5-S7 dashboard item 5 and §5-S8. The ledger grades us in public.

   The reliability diagram is the chart that matters: a system claiming 30%
   should be right 30% of the time, and the diagonal is where that lives. One
   series, so no legend — the title names it; the diagonal is a reference, not
   a series. Bins with no data are not drawn rather than drawn at zero. */

function Reliability({ rows }) {
  const pts = rows.filter((r) => r.n > 0 && r.predicted != null)
  if (pts.length === 0) return null

  const S = 148           // plot size
  const P = 22            // padding for axes
  const x = (v) => P + v * (S - P - 6)
  const y = (v) => S - P - v * (S - P - 6)
  const maxN = Math.max(...pts.map((r) => r.n))

  return (
    <figure className="reliability">
      <svg viewBox={`0 0 ${S} ${S}`} role="img"
           aria-label="Reliability diagram: claimed probability against observed frequency">
        {/* perfect-reliability reference */}
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)}
              stroke="var(--ink-faint)" strokeWidth="1" strokeDasharray="3 3" />
        {/* axes */}
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(0)} stroke="var(--hairline-hi)" strokeWidth="1" />
        <line x1={x(0)} y1={y(0)} x2={x(0)} y2={y(1)} stroke="var(--hairline-hi)" strokeWidth="1" />

        {/* the forecast's own curve */}
        <polyline
          points={pts.map((r) => `${x(r.predicted)},${y(r.observed)}`).join(' ')}
          fill="none" stroke="var(--series-1)" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round"
        />
        {pts.map((r, i) => (
          <circle key={i} cx={x(r.predicted)} cy={y(r.observed)}
                  r={4 + 3 * (r.n / maxN)}
                  fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth="1.5">
            <title>{`claimed ${r.predicted.toFixed(2)}, observed ${r.observed.toFixed(2)} (n=${r.n})`}</title>
          </circle>
        ))}

        <text x={x(0.5)} y={S - 4} textAnchor="middle"
              fill="var(--ink-muted)" fontSize="8" fontFamily="var(--mono)">CLAIMED</text>
        <text x={6} y={y(0.5)} textAnchor="middle" fill="var(--ink-muted)"
              fontSize="8" fontFamily="var(--mono)"
              transform={`rotate(-90 6 ${y(0.5)})`}>OBSERVED</text>
      </svg>
      <figcaption>
        Marker size is the number of forecasts in the bin. The dashed line is
        perfect reliability.
      </figcaption>
    </figure>
  )
}

export default function LedgerPanel({ ledger }) {
  if (!ledger) return null
  const unscored = !ledger.n_scored
  const bss = ledger.brier_skill_score
  const value = ledger.relative_value || {}

  return (
    <section className="panel rise rise-5" aria-label="Verification ledger">
      <div className="panel-head">
        <span className="label">S8 · public ledger</span>
        <span className="label">scored live</span>
      </div>
      <div className="panel-body">
        <div className="stat-row">
          <div className="stat">
            <div className="label">forecasts</div>
            <div className="v mono">{ledger.n_entries}</div>
          </div>
          <div className="stat">
            <div className="label">verified</div>
            <div className={`v mono ${unscored ? 'absent' : ''}`}>{ledger.n_scored}</div>
          </div>
          <div className="stat">
            <div className="label">brier</div>
            <div className={`v mono ${ledger.brier_score == null ? 'absent' : ''}`}>
              {ledger.brier_score == null ? '—' : ledger.brier_score.toFixed(3)}
            </div>
          </div>
          <div className="stat">
            <div className="label">skill</div>
            <div className="v mono" style={{
              color: bss == null ? 'var(--ink-faint)'
                   : bss >= 0 ? 'var(--good)' : 'var(--critical)',
            }}>
              {bss == null ? '—' : (bss >= 0 ? '+' : '') + bss.toFixed(3)}
            </div>
          </div>
        </div>

        {!unscored && <Reliability rows={ledger.reliability || []} />}

        {!unscored && Object.keys(value).length > 0 && (
          <div className="value-block">
            <div className="label" style={{ marginBottom: 7 }}>
              realised value per user class
            </div>
            {Object.entries(value).map(([name, v]) => (
              <div className="value-row" key={name}>
                <span className="value-name">{name.replace(/_/g, ' ')}</span>
                <span className="value-meta mono">
                  {v.hits}h {v.false_alarms}fa {v.misses}m
                </span>
                <span className="value-v mono" style={{
                  color: v.value == null ? 'var(--ink-faint)'
                       : v.value > 0 ? 'var(--good)' : 'var(--critical)',
                }}>
                  {v.value == null ? '—' : (v.value >= 0 ? '+' : '') + v.value.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}

        <p className="note">{ledger.status}</p>
      </div>
    </section>
  )
}
