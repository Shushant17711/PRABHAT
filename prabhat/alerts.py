"""S6: turn probabilities into decisions per user class. S6b: hysteresis.

Each user class protects at cost C against a loss L. Under the classic
cost-loss model, acting pays off once the event probability exceeds
p* = C / L, so each class gets its own threshold. A district disaster
manager evacuates at a lower probability than a logistics operator reroutes
trucks.

A single threshold makes alerts flicker on and off as successive runs land
either side of p*. Responders learn to ignore an alert that does that, which
is the alert fatigue the problem statement names. S6b adds hysteresis: an
alert is raised at p* exactly as before, but once raised it is cleared only
when the probability falls below ``p_clear = p* - band``. Raising is
unchanged, so the first alert is never later than without the band. The
churn simulation measures how many notifications that saves and checks the
first alert is not delayed. A band narrower than one ensemble member (1/M)
cannot be resolved, and the result says so.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import numpy as np

from .cases import CaseSpec


@dataclass(frozen=True)
class UserClass:
    name: str
    label: str
    cost: float
    loss: float
    band: float

    @property
    def p_star(self) -> float:
        return self.cost / self.loss

    @property
    def p_raise(self) -> float:
        return self.p_star

    @property
    def p_clear(self) -> float:
        return max(self.p_star - self.band, 0.01)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(p_star=round(self.p_star, 4), p_raise=round(self.p_raise, 4),
                 p_clear=round(self.p_clear, 4))
        return d


USER_CLASSES: tuple[UserClass, ...] = (
    UserClass("district_dm", "District disaster management", cost=1.0, loss=12.0, band=0.06),
    UserClass("farmer_smallholder", "Smallholder farmer", cost=1.0, loss=4.0, band=0.10),
    UserClass("logistics_operator", "Logistics operator", cost=2.0, loss=5.0, band=0.15),
)
USER_CLASSES_BY_NAME = {u.name: u for u in USER_CLASSES}

ACTIONS = {
    "district_dm": {
        "cyclone": "pre-position NDRF teams, prepare evacuation of coastal blocks",
        "extreme_rain": "pre-position NDRF teams, alert low-lying wards",
        "heatwave": "open cooling centres, shift outdoor work hours",
        "coldwave": "open night shelters, stock fuel for warming points",
    },
    "farmer_smallholder": {
        "cyclone": "harvest mature crop early, secure livestock",
        "extreme_rain": "clear field drainage, delay fertiliser application",
        "heatwave": "irrigate in the evening, shade livestock",
        "coldwave": "light irrigation against frost, cover nurseries",
    },
    "logistics_operator": {
        "cyclone": "hold coastal shipments, reroute inland",
        "extreme_rain": "reroute around flood-prone corridors",
        "heatwave": "move dispatch to night hours, check reefer capacity",
        "coldwave": "plan for fog delays on northern corridors",
    },
}


def severity(p: float) -> str:
    return "severe" if p >= 0.7 else "moderate" if p >= 0.4 else "low"


def issue(spec: CaseSpec, prob: np.ndarray, lat: np.ndarray, lon: np.ndarray,
          leads: np.ndarray, verdict: str) -> tuple[list[dict], int]:
    """Alerts from a published (leads, ny, nx) exceedance field.

    Returns ``(alerts, n_suppressed)``. Under SUPPRESS nothing is issued and
    every class that would have been alerted is counted as suppressed.
    """
    li, iy, ix = np.unravel_index(int(np.argmax(prob)), prob.shape)
    p = float(prob[li, iy, ix])
    init = datetime.fromisoformat(spec.init_time.replace("Z", "+00:00"))
    valid = init + timedelta(hours=int(leads[li]))
    alerts, suppressed = [], 0
    for uc in USER_CLASSES:
        if p < uc.p_raise:
            continue
        if verdict == "SUPPRESS":
            suppressed += 1
            continue
        key = f"{spec.id}|{uc.name}|{spec.init_time}|{p:.3f}"
        alerts.append({
            "alert_id": f"{spec.id}-{uc.name}-{hashlib.sha256(key.encode()).hexdigest()[:8]}",
            "case_id": spec.id,
            "hazard": spec.hazard,
            "user_class": uc.name,
            "probability": round(p, 3),
            "severity": severity(p),
            "action": ACTIONS[uc.name][spec.hazard],
            "impact_field": spec.impact_field,
            "confidence_mode": "fine" if verdict == "PASS" else "coarse",
            "centre": [round(float(lat[iy]), 3), round(float(lon[ix]), 3)],
            "radius_km": 5.0 if verdict == "PASS" else 12.0,
            "lead_hour": int(leads[li]),
            "issued_at": spec.init_time,
            "valid_at": valid.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return alerts, suppressed


def _count_switches(states: np.ndarray) -> int:
    """Number of on/off transitions along the run axis (axis 0), starting off."""
    padded = np.concatenate([np.zeros((1,) + states.shape[1:], bool), states])
    return int(np.sum(padded[1:] != padded[:-1]))


def _first_on(states: np.ndarray) -> np.ndarray:
    on = states.any(axis=0)
    return np.where(on, states.argmax(axis=0), -1)


def churn(spec: CaseSpec, peak_prob: np.ndarray, n_members: int,
          n_runs: int = 12) -> list[dict]:
    """Simulate ``n_runs`` successive 6-hourly runs converging on ``peak_prob``.

    ``peak_prob`` is each footprint cell's final exceedance probability. Early
    runs see a weaker signal, and every run's probability is a binomial draw
    of M members, which is the sampling noise that makes a lone threshold
    flicker.
    """
    cells = peak_prob[peak_prob >= 0.02]
    out = []
    for i, uc in enumerate(USER_CLASSES):
        rng = np.random.default_rng(spec.seed * 31 + i)
        ramp = 0.5 + 0.5 * np.arange(n_runs) / (n_runs - 1)
        truth = np.clip(ramp[:, None] * cells[None, :], 0, 1)
        sampled = rng.binomial(n_members, truth) / n_members  # (runs, cells)

        plain = sampled >= uc.p_star
        band = np.zeros_like(plain)
        state = np.zeros(cells.shape, bool)
        for r in range(n_runs):
            state = np.where(state, sampled[r] >= uc.p_clear, sampled[r] >= uc.p_raise)
            band[r] = state

        f_plain, f_band = _first_on(plain), _first_on(band)
        both = (f_plain >= 0) & (f_band >= 0)
        delay = float(np.mean(f_band[both] - f_plain[both])) if both.any() else 0.0
        out.append({
            "user_class": uc.name,
            "n_runs": n_runs,
            "n_cells": int(cells.size),
            "churn_without": _count_switches(plain),
            "churn_with": _count_switches(band),
            "mean_delay_runs": round(delay, 2),
            "lead_time_preserved": bool(delay <= 1.0),
            "p_raise": round(uc.p_raise, 4),
            "p_clear": round(uc.p_clear, 4),
            "band_resolvable": bool(uc.p_raise - uc.p_clear >= 1.0 / n_members),
        })
    return out
