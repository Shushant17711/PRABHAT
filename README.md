# PRABHAT

**Tracked-object extreme-weather anomaly detection with runtime hallucination gates.**

Smart India Hackathon problem **SIH26078** (MoES / NCMRWF) · Team Orbit

PRABHAT follows an extreme-weather anomaly through an ensemble forecast as a
single object, downscales it from about 12 km to 5 km, and checks at runtime
that the 5 km field is still faithful to the ensemble before publishing it.
Alerts are issued per user class, held steady with hysteresis so they don't
flicker, exported as CAP 1.2, and logged to a hash-chained ledger that scores
the system's own forecasts.

> **All forecast data in this repository is synthetic.** NCMRWF's NEPS-G
> ensemble and an ERA5 climatology are not included, so a 20-member synthetic
> ensemble stands in for them. The API and dashboard say this on every case. Read
> the numbers as a demonstration of the pipeline, not as forecasts.

## The problem

Machine-learning weather models and upsamplers suffer from *spectral
smoothing*: averaging over uncertainty removes small-scale variance, which is
exactly where extremes live. A smoothed 5 km field looks plausible and
understates the peak. PRABHAT's answer is to measure that failure on every run
and refuse to publish a field that shows it.

## Pipeline

| Stage | Module | What it does |
|---|---|---|
| S0 input | `prabhat/ensemble.py` | Synthetic ensemble: 20 members + a "nature run", 0.12° grid, 6-hourly to T+120 h, power-law weather texture |
| S1 tracking | `prabhat/tracking.py` | Ensemble exceedance probability → connected region per lead → a 4-D *anomaly tube* (bbox, centroid, confidence, intensity per lead) |
| S1 EFI | `prabhat/efi.py` | Extreme Forecast Index against a climatology (simulated normal baseline here) |
| S2 analogues | `prabhat/analogues.py` | **Stub.** Ranks a small catalogue of past Indian events by distance |
| S4 downscaling | `prabhat/downscale.py` | 12 km → 5 km. Cubic interpolation, then fine-scale detail injected at the power-law slope fitted to the resolved spectrum (RainFARM-style) |
| S5 gates | `prabhat/gates.py` | **G1 spectral fidelity:** does the 5 km field have the fine-scale power its own spectrum predicts? **G2 cross-scale consistency:** does the 5 km exceedance region still overlap the ensemble's, in the same place? |
| S6 alerts | `prabhat/alerts.py` | One cost-loss threshold `p* = C/L` per user class (district disaster management, smallholder farmer, logistics operator) |
| S6b hysteresis | `prabhat/alerts.py` | Raise at `p*`, clear only below `p* − band`. A simulation of successive runs measures the notifications saved |
| S7 API + dashboard | `prabhat/api/`, `dashboard/` | FastAPI service and a React + MapLibre console |
| S8 ledger | `prabhat/ledger.py` | Append-only JSON Lines, SHA-256 hash-chained; Brier score, reliability diagram, relative economic value |
| CAP export | `prabhat/cap.py` | Alerts as Common Alerting Protocol 1.2 XML, marked `Exercise` |

### Gate verdicts

| G1 spectral | G2 cross-scale | Verdict | Published |
|---|---|---|---|
| pass | pass | `PASS` | 5 km field and fine-confidence alerts |
| fail | pass | `DEGRADE` | 12 km probabilities only, coarse-confidence alerts |
| any | fail | `SUPPRESS` | nothing at 5 km, no alerts |

Every case reports what it could not do (synthetic input, simulated
climatology, gate downgrades) in a limitations panel that is shown even when
it is empty.

## Demo cases

| Case | Hazard | Gate |
|---|---|---|
| `bay_of_bengal_cyclone` | cyclone, wind > 62 kt | PASS (SFS 0.93) |
| `konkan_extreme_rain` | rainfall > 100 mm / 12 h | PASS (SFS 0.81) |
| `rajasthan_heatwave` | max temperature > 45 °C | PASS (SFS 0.98) |
| `punjab_coldwave` | min temperature < 4 °C | PASS (SFS 0.97) |
| `konkan_interp_control` | the rainfall case, downscaled by plain interpolation | **DEGRADE** (SFS 0.06) |

The control case shows the gate catching spectral smoothing. Interpolation
keeps the footprint but loses the fine-scale power, so the 5 km field is
withheld.

## Quick start

Requires Python ≥ 3.11 and Node ≥ 18.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

uvicorn prabhat.api.app:app --reload     # API on http://127.0.0.1:8000, docs at /docs
```

In a second terminal:

```bash
cd dashboard
npm ci
npm run dev                              # http://localhost:5173, proxies /v1 to :8000
```

Or build the dashboard once (`npm run build`) and the API serves it at
`http://127.0.0.1:8000/`.

The first request to `/v1/status` computes all five cases (about 10 s). After
that, results are cached for the life of the process. The ledger is written to
`artifacts/ledger.jsonl`. Set `PRABHAT_LEDGER` to put it somewhere else.

Dashboard keys: `space` plays the forecast, and `←` / `→` step through lead times.

## API

| Route | Returns |
|---|---|
| `GET /v1/cases` | demo cases |
| `GET /v1/user-classes` | user classes with `p*`, `p_raise` and `p_clear` |
| `GET /v1/status` | per-case run status, stub stages and limitations |
| `GET /v1/tubes?case=` | anomaly tubes |
| `GET /v1/tubes/{id}/gate` | S5 verdict and metrics |
| `GET /v1/tubes/{id}/exceedance` | published probability raster, per lead |
| `GET /v1/tubes/{id}/efi` | EFI field |
| `GET /v1/tubes/{id}/analogues` | closest historical events (stub) |
| `GET /v1/alerts?case=&user_class=` | issued alerts |
| `GET /v1/churn?case=` | hysteresis churn simulation |
| `GET /v1/ledger/summary` | Brier score, reliability and relative value; whether the hash chain is intact |
| `GET /v1/cap/{alert_id}.xml` | CAP 1.2 message |

## Tests

```bash
pytest          # 18 tests, about 15 s
```

They cover the spectral and EFI maths, the gate verdicts, the claim that
hysteresis never delays the first alert, every API route, and the ledger
detecting an edited entry.

## Limitations

- **Synthetic input.** No NEPS-G, NCUM or ERA5 data is ingested. The ensemble
  generator is shaped like real ensembles (growing position spread, intensity
  spread, power-law texture) but is not weather.
- **The ledger scores a twin experiment.** Hindcasts are scored against the
  synthetic nature run they were drawn with. That checks calibration and the
  scoring code. It is not skill against observations.
- **Statistical downscaler.** S4 is a spectral (RainFARM-style) method, not the
  diffusion model the problem statement suggests. A trained model would plug in
  behind the same `Downscaler` interface, and the S5 gates would judge it the
  same way.
- **S2 analogues are a stub.** S2 ranks a hand-written catalogue by distance; it uses no learned embedding.
- **No physics-constraint stage** and no GNN. See `PROBLEM_STATEMENT.md`.

## Repository layout

```
prabhat/            pipeline stages S0–S8, CAP export
prabhat/api/        FastAPI app
dashboard/          React + Vite + MapLibre console (basemap bundled, works offline)
tests/              pytest suite
PROBLEM_STATEMENT.md  the SIH26078 brief and where the design diverges from it
```

`PROBLEM_STATEMENT.md` and the code comments in `dashboard/` refer to a
`DESIGN.md` and a task list that are not part of this repository. The status
table in `PROBLEM_STATEMENT.md` describes an earlier version of the code.
