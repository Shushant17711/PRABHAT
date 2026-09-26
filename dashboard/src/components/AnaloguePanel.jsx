import React from 'react'

/* DESIGN §5-S7 dashboard item 4 — free explainability for a black-box model:
   "resembles Amphan 2020 at T-60h (0.89)". */

export default function AnaloguePanel({ analogues, isStub }) {
  return (
    <section className="panel rise rise-3" aria-label="Historical analogues">
      <div className="panel-head">
        <span className="label">S2 · closest analogues</span>
        {isStub && (
          <span className="badge badge-stub">
            <span className="badge-dot" /> stub
          </span>
        )}
      </div>

      {analogues.length === 0 && <p className="no-alert">No analogues retrieved.</p>}

      {analogues.map((a) => (
        <div className="analog" key={a.event_id}>
          <div>
            <div className="analog-name">{a.display_name}</div>
            <div className="analog-stage">{a.analog_stage}</div>
          </div>
          <div className="analog-sim">
            <div className="v">{a.similarity.toFixed(2)}</div>
            <div className="sim-track">
              <div className="sim-fill" style={{ width: `${a.similarity * 100}%` }} />
            </div>
          </div>
        </div>
      ))}
    </section>
  )
}
