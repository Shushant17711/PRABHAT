# SIH26078 — the official problem statement, and where we diverge

Source: the SIH portal listing for **SIH26078**, Ministry of Earth Sciences
(MoES) / NCMRWF, theme *Smart Automation*.

`DESIGN.md` was written before we had this text, and it disagrees with the
problem statement in three places that matter. **Read this alongside DESIGN §2
and §12.** Where they conflict, the problem statement wins on *what the sponsor
asked for*; DESIGN's reasoning still stands on *how we build it*. But each
divergence has to be a deliberate, defensible choice rather than an oversight —
NCMRWF judges will know their own problem statement.

---

## What the PS asks for, and what this repo already has

| PS requirement | Status |
|---|---|
| 4D bounding boxes around evolving threats, from ensemble (EPS) data | **Built** — `AnomalyTube` (§4.2) is exactly this: per-lead bbox, centroid, intensity, carried as one object |
| Categorised alerts — low / moderate / severe | **Built** — `Alert.severity` is that three-level scale |
| 5 km impact radius, pinpoint coordinate at the anomaly core | **Built** — `Alert.centre` + `radius_km = 5.0` |
| Lightweight production REST API | **Built** — `prabhat/api/app.py`, nine routes; the OpenAPI schema *is* the data contract |
| Visualisation & alert dashboard | **Built** — `dashboard/`, tube animation, probability raster, gate/analogue/ledger panels |
| Eliminating alert fatigue for the NDRF | **Designed, not built** — this is our hysteresis contribution (§5-S6b, TASKS 13.2); still a stub |
| Diffusion downscaling 12 km → 5 km preserving amplitudes | **Stub** — TASKS task 11 |
| Physics-informed constraints | **Designed** — and we go further than asked; see divergence 3 |
| GNN on icosahedral mesh + EFI vs 30-yr ERA5 baseline | **Divergences 1 and 2** |

The PS's own framing of the core problem — *standard deep learning models suffer
from spectral smoothing, which destroys the extreme amplitudes* — is precisely
the failure mode our **G1 spectral-fidelity gate** detects at runtime. That
alignment should lead the pitch: they named the disease, we built the alarm.

---

## Divergence 1 — the forecast input dataset

**PS:** NCMRWF **NEPS-G** (12 km global ensemble) and **NCUM** (12 km
deterministic), with IMDAA / ERA5 as the climatological baseline.

**DESIGN:** Google WeatherNext 3 forecasts, WeatherNext 2 frozen weights.

This is the most consequential difference, and it cuts in our favour:

- NEPS-G is **the sponsor's own operational ensemble**. Building on it deletes
  the whole "strategic dependency on a closed US model" problem that DESIGN §12
  spends a prepared answer defending.
- It removes our largest schedule risk. DESIGN §11 lists the WeatherNext access
  request as a medium-likelihood blocker; NEPS-G and NCUM come from the very
  organisation that set this problem.
- The `ForecastCube` contract (§4.1) is source-agnostic by construction, and
  `prabhat/data/normalise.py` already maps arbitrary source conventions onto it.
  **Switching input dataset is a data-layer change, not an architecture change.**
  Nothing in S1–S8 moves.

**Recommendation:** make NEPS-G the primary input; keep WeatherNext as an
optional comparison rather than dropping it, since an independent 5 km
temperature field is still a useful validation target (§12). Add NEPS-G and
NCUM rows to `data/SOURCES.md` and pursue access through NCMRWF.

## Divergence 2 — how Stage 1 finds the anomaly

**PS:** message-passing **GNN on an icosahedral mesh**, computing an **Extreme
Forecast Index (EFI)** against a 30-year ERA5 baseline distribution to isolate
standard deviations, then drawing the bounding box.

**DESIGN:** DETR-style set prediction with learned queries over frozen
WeatherNext-2 mesh latents (§5-S1).

Both are mesh-based, and both avoid the lat/lon grid distortion the PS objects
to. The substantive gap is the **EFI**, and we should simply adopt it — it is
cheap, standard, and explicitly requested. EFI compares the ensemble's CDF
against the model-climate CDF for that location and date. It is explainable to a
meteorologist in one sentence, and it gives an anomaly measure our current
ensemble-extremum tracker does not have.

**Recommendation:** add `prabhat/anomaly/efi.py` computed against the ERA5
baseline and feed it as the *detection signal* into S1, leaving the tube schema
unchanged. This is additive — it strengthens the tracker whichever architecture
wins — and it is a concrete answer to "where is the EFI you promised?".

## Divergence 3 — where the physics constraint is applied

**PS:** embed conservation laws **in the loss function**; penalise physically
impossible states.

**DESIGN:** a loss penalty is soft and the model can pay it, so **project onto
the constraint set at sampling time**, after every reverse diffusion step
(§5-S4).

We are a strict superset of what was asked. This is a pitch asset, not a
divergence to hide:

> "The problem statement asks for conservation in the loss. A loss penalty is
> soft — the model can pay it and still emit a physically impossible field. We
> implement the penalty *and* project onto the constraint set at every sampling
> step, so conservation holds by construction at inference rather than in
> expectation over training."

Keep the loss penalty too, so the claim is "both", not "instead".

---

## Two things the PS hands us for free

1. **"Eliminating alert fatigue for the NDRF"** is called out as a headline
   societal impact. Our hysteresis band (§5-S6b) is a direct, quantified answer,
   and the churn metric is the number for the slide. This promotes hysteresis
   from "our clever extra" to "the thing they asked for".
2. **The PS names four deliverables** — tracking core, downscaling core,
   dashboard, alerting API. This repo maps onto them one-to-one. Present it in
   their four boxes, not our eight stages.

## What the PS does not ask for, and we should keep anyway

The gates (S5), analogue retrieval (S2) and the public ledger (S8) are ours, not
theirs. DESIGN §13.5 says cut S2 before S5 if time runs short; the PS's own
emphasis on spectral smoothing makes S5 easier to justify, not harder. Keep the
ledger — it is the cheapest credibility available in front of a government
sponsor.
