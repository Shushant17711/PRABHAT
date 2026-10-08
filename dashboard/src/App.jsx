import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api } from './api.js'
import MapView from './components/MapView.jsx'
import GatePanel from './components/GatePanel.jsx'
import AlertsPanel from './components/AlertsPanel.jsx'
import AnaloguePanel from './components/AnaloguePanel.jsx'
import LedgerPanel from './components/LedgerPanel.jsx'
import ChurnPanel from './components/ChurnPanel.jsx'

const HAZARD_LABEL = {
  cyclone: 'cyclone',
  heatwave: 'heat wave',
  coldwave: 'cold wave',
  extreme_rain: 'extreme rain',
}

export default function App() {
  const [cases, setCases] = useState([])
  const [userClasses, setUserClasses] = useState([])
  const [status, setStatus] = useState([])
  const [caseId, setCaseId] = useState(null)
  const [tube, setTube] = useState(null)
  const [gate, setGate] = useState(null)
  const [analogues, setAnalogues] = useState([])
  const [raster, setRaster] = useState(null)
  const [efi, setEfi] = useState(null)
  const [layer, setLayer] = useState('probability')
  const [alerts, setAlerts] = useState([])
  const [ledger, setLedger] = useState(null)
  const [churn, setChurn] = useState([])
  const [selectedClass, setSelectedClass] = useState(null)
  const [leadIndex, setLeadIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState(null)

  // --- bootstrap ---------------------------------------------------------
  useEffect(() => {
    Promise.all([api.cases(), api.userClasses(), api.status(), api.ledger()])
      .then(([c, u, s, l]) => {
        setCases(c)
        setUserClasses(u)
        setStatus(s)
        setLedger(l)
        setCaseId((prev) => prev ?? c[0]?.id ?? null)
      })
      .catch((e) => setError(e.message))
  }, [])

  // --- per-case load -----------------------------------------------------
  useEffect(() => {
    if (!caseId) return
    let cancelled = false
    setPlaying(false)
    setLeadIndex(0)
    ;(async () => {
      try {
        const tubes = await api.tubes(caseId)
        const t = tubes[0]
        if (cancelled) return
        setTube(t ?? null)
        if (!t) {
          setGate(null); setAnalogues([]); setRaster(null); setAlerts([])
          return
        }
        const [g, an, ras, al] = await Promise.all([
          api.gate(t.tube_id),
          api.analogues(t.tube_id),
          api.exceedance(t.tube_id),
          api.alerts(caseId),
        ])
        if (cancelled) return
        setGate(g); setAnalogues(an); setRaster(ras); setAlerts(al)

        // Open on the lead the warning is actually about, not on T+000.
        // For an accumulation like rainfall, lead 0 is zero by definition —
        // nothing has fallen at initialisation — so the first frame would be
        // an empty map at 0% for a case whose whole point is a 67% chance of
        // 100 mm. The forecaster still has the full timeline to scrub.
        if (ras?.values?.length) {
          let best = 0
          let bestMax = -1
          ras.values.forEach((plane, i) => {
            let m = 0
            for (const row of plane) for (const v of row) if (v > m) m = v
            if (m > bestMax) { bestMax = m; best = i }
          })
          setLeadIndex(best)
        }

        // EFI needs a climatology, so it may legitimately be absent.
        setEfi(null)
        api.efi(t.tube_id).then((e) => { if (!cancelled) setEfi(e) }).catch(() => {})

        // Churn runs a multi-run simulation, so let it land on its own.
        setChurn([])
        api.churn(caseId).then((c) => { if (!cancelled) setChurn(c) }).catch(() => {})
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    })()
    return () => { cancelled = true }
  }, [caseId])

  const leads = raster?.lead_hours ?? tube?.points.map((p) => p.lead_hour) ?? [0]
  const maxIndex = Math.max(0, leads.length - 1)

  // --- lead-time animation ----------------------------------------------
  const timer = useRef(null)
  useEffect(() => {
    if (!playing) return
    timer.current = setInterval(() => {
      setLeadIndex((i) => (i >= maxIndex ? 0 : i + 1))
    }, 260)
    return () => clearInterval(timer.current)
  }, [playing, maxIndex])

  const step = useCallback(
    (d) => {
      setPlaying(false)
      setLeadIndex((i) => Math.max(0, Math.min(maxIndex, i + d)))
    },
    [maxIndex],
  )

  // Keyboard transport — a console should be drivable without the mouse.
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT') return
      if (e.key === 'ArrowRight') step(1)
      else if (e.key === 'ArrowLeft') step(-1)
      else if (e.key === ' ') { e.preventDefault(); setPlaying((p) => !p) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step])

  const activeCase = cases.find((c) => c.id === caseId)
  const runStatus = status.find((s) => s.case_id === caseId)
  const visibleAlerts = selectedClass
    ? alerts.filter((a) => a.user_class === selectedClass)
    : alerts
  const focusAlert = visibleAlerts[0] ?? null

  const peakP = useMemo(() => {
    if (!raster) return null
    const plane = raster.values[leadIndex]
    if (!plane) return null
    let m = 0
    for (const row of plane) for (const v of row) if (v > m) m = v
    return m
  }, [raster, leadIndex])

  const stubStages = runStatus?.stub_stages ?? []
  const isStub = (s) => stubStages.some((x) => x.startsWith(s))
  // What this run could NOT do. The system's whole claim is that it says so
  // rather than presenting a confident-looking field it cannot stand behind,
  // and that claim is worth nothing if the admission is only in a log file.
  const degradations = runStatus?.degradations ?? []

  if (error) {
    return (
      <div className="center-msg">
        <div>
          <h2>The console cannot reach the pipeline.</h2>
          <p style={{ maxWidth: 460 }}>{error}</p>
          <p className="label" style={{ marginTop: 18 }}>start the API, then reload</p>
          <code>uvicorn prabhat.api.app:app --reload</code>
        </div>
      </div>
    )
  }

  if (!activeCase) {
    return <div className="center-msg"><h2>Establishing link…</h2></div>
  }

  return (
    <div className="app">
      {/* ------------------------------ masthead ------------------------ */}
      <header className="masthead">
        <h1 className="wordmark">PRABHAT<span>.</span></h1>
        <div className="masthead-sub">
          tracked-object anomaly detection<br />
          SIH26078 · team orbit
        </div>

        <nav className="cases" role="tablist" aria-label="Demo cases">
          {cases.map((c) => (
            <button
              key={c.id}
              role="tab"
              className="case-tab"
              aria-selected={c.id === caseId}
              onClick={() => setCaseId(c.id)}
            >
              {c.id.replace(/_/g, ' ')}
              <small>{HAZARD_LABEL[c.hazard] ?? c.hazard}</small>
            </button>
          ))}
        </nav>

        <div className="spacer" />

        {runStatus?.is_synthetic && (
          <span className="badge badge-synthetic" title="No real forecast data is loaded">
            <span className="badge-dot" /> synthetic input
          </span>
        )}
      </header>

      {/* ------------------------------- main --------------------------- */}
      <div className="main">
        <div className="stage">
          <div className="map-wrap">
            <MapView
              tube={tube}
              raster={raster}
              efi={efi}
              layer={layer}
              leadIndex={leadIndex}
              alertCentre={focusAlert?.centre ?? null}
              bbox={activeCase.domain_bbox}
            />

            <div className="map-readout">
              <div className="label">peak exceedance</div>
              <div className="big" style={{ color: peakP ? 'var(--seq-6)' : 'var(--ink-faint)' }}>
                {peakP == null ? '—' : `${(peakP * 100).toFixed(0)}%`}
              </div>
              <div className="label" style={{ marginTop: 4 }}>
                {raster?.field?.replace(/_/g, ' ') ?? ''}
              </div>
            </div>

            <div className="map-legend">
              <div className="layer-toggle" role="group" aria-label="Map layer">
                <button
                  className="layer-btn"
                  aria-pressed={layer === 'probability'}
                  onClick={() => setLayer('probability')}
                >
                  probability
                </button>
                <button
                  className="layer-btn"
                  aria-pressed={layer === 'efi'}
                  disabled={!efi}
                  title={efi ? 'Extreme Forecast Index' : 'no climatology built'}
                  onClick={() => setLayer('efi')}
                >
                  EFI
                </button>
              </div>

              {layer === 'probability' ? (
                <>
                  <div className="label">exceedance probability</div>
                  <div className="ramp" />
                  <div className="ramp-scale">
                    <span>0</span><span>0.5</span><span>1.0</span>
                  </div>
                  <div
                    className="label"
                    style={{ marginTop: 8, color: 'var(--warning)', letterSpacing: '0.08em' }}
                  >
                    uncalibrated · {raster?.n_members ?? 0} members
                  </div>
                </>
              ) : (
                <>
                  <div className="label">extreme forecast index</div>
                  <div className="ramp ramp-efi" />
                  <div className="ramp-scale">
                    <span>−1</span><span>0</span><span>+1</span>
                  </div>
                  <div
                    className="label"
                    style={{ marginTop: 8, color: 'var(--warning)', letterSpacing: '0.08em' }}
                  >
                    {efi?.is_synthetic_baseline ? 'simulated baseline' : 'ERA5 baseline'}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* --------------------------- transport ---------------------- */}
          <div className="transport">
            <button className="tbtn" onClick={() => step(-1)} aria-label="Previous lead time">‹</button>
            <button
              className="tbtn"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? 'Pause' : 'Play forecast'}
              style={{ borderColor: playing ? 'var(--serious)' : undefined }}
            >
              {playing ? '❚❚' : '▶'}
            </button>
            <button className="tbtn" onClick={() => step(1)} aria-label="Next lead time">›</button>

            <div className="scrub">
              <input
                type="range"
                min={0}
                max={maxIndex}
                value={leadIndex}
                onChange={(e) => { setPlaying(false); setLeadIndex(+e.target.value) }}
                aria-label="Forecast lead time"
              />
              <div className="ticks">
                {[0, 0.25, 0.5, 0.75, 1].map((f) => (
                  <span key={f}>T+{leads[Math.round(f * maxIndex)] ?? 0}h</span>
                ))}
              </div>
            </div>

            <div className="lead-readout">
              T+{String(leads[leadIndex] ?? 0).padStart(3, '0')}
              <small> h</small>
            </div>
          </div>
        </div>

        {/* ------------------------------ rail --------------------------- */}
        <aside className="rail">
          <GatePanel gate={gate} isStub={isStub('S5')} />
          <AlertsPanel
            alerts={alerts}
            userClasses={userClasses}
            selected={selectedClass}
            onSelect={setSelectedClass}
          />
          <AnaloguePanel analogues={analogues} isStub={isStub('S2')} />
          <ChurnPanel churn={churn} />
          <LedgerPanel ledger={ledger} />
        </aside>
      </div>

      {/* ------------------------- what this run cannot do ---------------
          Always rendered, including when the list is empty. Hiding the panel
          on a clean run makes "this run had no limitations" and "the panel is
          broken / the case never reported" look identical, which is the one
          thing a self-reporting honesty panel must never do. An explicit
          "none" is a claim the run is standing behind. */}
      <section
        className={degradations.length ? 'caveats' : 'caveats caveats-clean'}
        aria-label="Limitations of this run"
      >
        <div className="caveats-head">
          <span className="caveats-mark" aria-hidden="true" />
          what this run could not do
          <span className="caveats-count">{degradations.length}</span>
        </div>
        {degradations.length === 0 ? (
          <p className="caveats-none">
            {runStatus
              ? 'Nothing to report: every stage ran on real data at full capability.'
              : 'No run status for this case — limitations unknown, which is not the same as none.'}
          </p>
        ) : (
          <ul>
            {degradations.map((d, i) => {
              const [stage, rest] = d.split(/:\s(.+)/s)
              const [reason, consequence] = (rest ?? '').split(' -> ')
              return (
                <li key={i}>
                  <b>{stage}</b>
                  <span className="caveat-reason">{reason}</span>
                  {consequence && (
                    <span className="caveat-consequence">{consequence}</span>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {/* --------------------------- status strip ----------------------- */}
      <footer className="strip">
        <span><b>{runStatus?.mode ?? '—'}</b> mode</span>
        <span className="sep">·</span>
        <span>source <b>{runStatus?.source ?? '—'}</b></span>
        <span className="sep">·</span>
        <span>{runStatus?.n_tubes ?? 0} tube · {runStatus?.n_alerts ?? 0} alerts · {runStatus?.n_suppressed ?? 0} suppressed</span>
        <span className="sep">·</span>
        <span>{runStatus?.elapsed_s?.toFixed(2) ?? '—'}s</span>
        <span className="sep">·</span>
        <span style={{ color: 'var(--serious)' }}>
          stubs: {stubStages.map((s) => s.split(' ')[0]).join(' ') || 'none'}
        </span>
        <div className="spacer" />
        <span>space play · ← → step</span>
      </footer>
    </div>
  )
}
