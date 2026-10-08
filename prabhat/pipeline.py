"""Run every stage for one case and collect what the API serves."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from . import alerts as s6
from .analogues import retrieve
from .cases import CASES_BY_ID, CaseSpec
from .downscale import FINE_RES, Downscaler, NotFittable, fine_axes
from .efi import efi_field
from .ensemble import COARSE_RES, generate
from .gates import cross_scale, decide, spectral_fidelity
from .tracking import Tube, track

STUB_STAGES = [
    "S2 analogue retrieval: hand-written catalogue ranked by distance, no learned embedding",
]
ALWAYS_DEGRADED = [
    "S0 input: NEPS-G and NCUM are not ingested; a 20-member synthetic ensemble "
    "stands in -> the numbers show how the pipeline behaves, not real weather",
    "S1 EFI: no ERA5 climatology on disk; EFI uses a simulated normal baseline "
    "-> read EFI values as illustrative",
]


MAX_RASTER_CELLS = 72  # per side; the dashboard draws one polygon per cell


def _thin(n: int) -> int:
    return max(1, -(-n // MAX_RASTER_CELLS))


@dataclass
class CaseResult:
    spec: CaseSpec
    tubes: list[Tube]
    efi: dict | None = None
    gate: dict | None = None
    raster: dict | None = None
    analogues: list[dict] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)
    churn: list[dict] = field(default_factory=list)
    status: dict = field(default_factory=dict)


def _crop(lat, lon, lat_f, lon_f):
    ys = np.flatnonzero((lat >= lat_f[0] - 1e-6) & (lat <= lat_f[-1] + 1e-6))
    xs = np.flatnonzero((lon >= lon_f[0] - 1e-6) & (lon <= lon_f[-1] + 1e-6))
    return ys, xs


def run(spec: CaseSpec, downscaler: str = "spectral") -> CaseResult:
    t0 = time.perf_counter()
    ens = generate(spec)
    tubes = track(ens)
    res = CaseResult(spec=spec, tubes=tubes, efi=efi_field(ens))
    degradations = list(ALWAYS_DEGRADED)
    n_suppressed = 0

    if tubes:
        tube = tubes[0]
        lat_f, lon_f = fine_axes(tube.envelope, spec.domain_bbox)
        coarse_prob = ens.exceed(ens.members).mean(axis=0)  # (L, ny, nx)
        ys, xs = _crop(ens.lat, ens.lon, lat_f, lon_f)
        env_prob = coarse_prob[:, ys][:, :, xs]

        # S4: downscale every member at every lead.
        ds = Downscaler(spec, method=downscaler)
        M, L = ens.members.shape[:2]
        fine = np.empty((M, L, len(lat_f), len(lon_f)), np.float32)
        rng = np.random.default_rng(spec.seed + 1)
        try:
            for m in range(M):
                for li in range(L):
                    fine[m, li] = ds(ens.members[m, li], ens.lat, ens.lon, lat_f, lon_f, rng)
        except NotFittable as exc:
            degradations.append(
                f"S4 downscaling: {exc}, so it fell back to interpolation "
                f"-> fine-scale extremes are smoothed")
            ds = Downscaler(spec, method="interp")
            for m in range(M):
                for li in range(L):
                    fine[m, li] = ds(ens.members[m, li], ens.lat, ens.lon, lat_f, lon_f, rng)
        fine_prob = ens.exceed(fine).mean(axis=0)

        # S5: gate at the lead where the ensemble is most sure of the event.
        peak = int(np.argmax(env_prob.reshape(L, -1).max(axis=1)))
        sfs = float(np.median([spectral_fidelity(fine[m, peak]) for m in range(M)]))
        iou, dist = cross_scale(coarse_prob[peak], ens.lat, ens.lon,
                                fine_prob[peak], lat_f, lon_f)
        gate = decide(sfs, iou, dist, int(ens.leads[peak]), ds.method)
        res.gate = gate.to_dict()
        if gate.verdict != "PASS":
            consequence = ("coarse 12 km probabilities only" if gate.verdict == "DEGRADE"
                           else "no 5 km field and no alerts published")
            degradations.append(f"S5 gate {gate.verdict}: {gate.reason} -> {consequence}")

        if gate.verdict == "PASS":
            values, r_lat, r_lon, res_km = fine_prob, lat_f, lon_f, 5
        else:
            values, r_lat, r_lon, res_km = env_prob, ens.lat[ys], ens.lon[xs], 12
        sy, sx = _thin(len(r_lat)), _thin(len(r_lon))
        res.raster = {
            "tube_id": tube.tube_id,
            "field": spec.impact_field,
            "verdict": gate.verdict,
            "resolution_km": res_km,
            "n_members": int(M),
            "lead_hours": [int(x) for x in ens.leads],
            "lat": np.round(r_lat[::sy], 3).tolist(),
            "lon": np.round(r_lon[::sx], 3).tolist(),
            "values": np.round(values[:, ::sy, ::sx], 2).tolist(),
        }

        # S6 / S6b
        res.alerts, n_suppressed = s6.issue(spec, values, r_lat, r_lon, ens.leads, gate.verdict)
        res.churn = s6.churn(spec, env_prob.max(axis=0), n_members=M)
        res.analogues = retrieve(tube)
    else:
        degradations.append("S1 tracking: no anomaly crossed the detection threshold "
                            "-> nothing downstream ran")

    res.status = {
        "case_id": spec.id,
        "mode": "synthetic",
        "source": f"synthetic {ens.members.shape[0]}-member ensemble at "
                  f"{COARSE_RES:g}° (stand-in for NEPS-G), downscaled to {FINE_RES:g}°",
        "is_synthetic": True,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "n_tubes": len(tubes),
        "n_alerts": len(res.alerts),
        "n_suppressed": n_suppressed,
        "verdict": res.gate["verdict"] if res.gate else None,
        "stub_stages": list(STUB_STAGES),
        "degradations": degradations,
    }
    return res


# A control case: the same rainfall event downscaled by plain interpolation.
# Interpolation smooths away the fine-scale extremes, and the S5 gate should
# refuse to publish its 5 km field. It exists so the demo shows the gate firing.
CONTROLS = {"konkan_interp_control": ("konkan_extreme_rain", "interp")}


def case_ids() -> list[str]:
    return list(CASES_BY_ID) + list(CONTROLS)


def case_spec(case_id: str) -> CaseSpec:
    base = CONTROLS.get(case_id, (case_id, None))[0]
    return CASES_BY_ID[base]


@lru_cache(maxsize=None)
def run_case(case_id: str) -> CaseResult:
    if case_id in CONTROLS:
        base, method = CONTROLS[case_id]
        res = run(CASES_BY_ID[base], downscaler=method)
        res.status["case_id"] = case_id
        for t in res.tubes:
            t.tube_id = t.tube_id.replace(base, case_id)
            t.case_id = case_id
        if res.raster:
            res.raster["tube_id"] = res.tubes[0].tube_id
        for a in res.alerts:
            a["case_id"] = case_id
            a["alert_id"] = a["alert_id"].replace(base, case_id)
        return res
    return run(CASES_BY_ID[case_id])
