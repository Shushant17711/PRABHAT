"""S8: the public verification ledger.

Every issued alert and every scored forecast is appended to a JSON Lines file.
Each entry carries the SHA-256 of the previous one, so editing or deleting a
past entry breaks the chain and ``verify()`` reports it. The point is that the
system's track record can be audited, not just asserted.

Scoring needs observations. None are ingested here, so the ledger is seeded
with a perfect-model twin experiment: synthetic hindcasts scored against the
nature run each one was generated with. That checks that the probabilities
are calibrated and the scoring code is correct. It says nothing about skill
against real weather, and the summary's ``status`` field states this.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .alerts import USER_CLASSES
from .cases import CASES
from .ensemble import generate

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "ledger.jsonl"
GENESIS = "0" * 64


def default_path() -> Path:
    return Path(os.environ.get("PRABHAT_LEDGER", DEFAULT_PATH))


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open() as f:
            return [json.loads(line) for line in f if line.strip()]

    def append(self, record: dict) -> dict:
        entries = self.entries()
        entry = dict(record, seq=len(entries),
                     prev_hash=entries[-1]["hash"] if entries else GENESIS)
        entry["hash"] = _digest(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def verify(self) -> bool:
        prev = GENESIS
        for i, e in enumerate(self.entries()):
            if e.get("seq") != i or e.get("prev_hash") != prev or _digest(e) != e.get("hash"):
                return False
            prev = e["hash"]
        return True

    def record_alert(self, alert: dict) -> None:
        """Append an issued alert once. Re-running the same case is a no-op."""
        if any(e.get("alert_id") == alert["alert_id"] for e in self.entries()):
            return
        self.append({"kind": "alert", **alert})


def _peak_lead(spec) -> int:
    return int(max(spec.amplitude, key=lambda p: p[1])[0] // 6 * 6)


def seed_hindcasts(ledger: Ledger, n_per_case: int = 6, max_cells: int = 300) -> int:
    """Append synthetic twin-experiment hindcasts. Returns the number added."""
    added = 0
    for spec in CASES:
        lead = _peak_lead(spec)
        for r in range(n_per_case):
            seed = spec.seed * 1000 + r
            ens = generate(spec, seed=seed, leads=np.array([lead]))
            prob = ens.exceed(ens.members[:, 0]).mean(axis=0).ravel()
            obs = ens.exceed(ens.nature[0]).ravel()
            rng = np.random.default_rng(seed)
            hot = np.flatnonzero((prob > 0) | obs)
            cold = np.flatnonzero((prob == 0) & ~obs)
            take = np.concatenate([hot, rng.choice(cold, size=min(len(cold), len(hot)), replace=False)])
            if len(take) > max_cells:
                take = rng.choice(take, size=max_cells, replace=False)
            ledger.append({
                "kind": "hindcast",
                "case_template": spec.id,
                "seed": seed,
                "lead_hour": lead,
                "forecasts": np.round(prob[take], 3).tolist(),
                "outcomes": obs[take].astype(int).tolist(),
            })
            added += 1
    return added


def relative_value(p, o, alpha: float) -> dict:
    """Richardson (2000) relative economic value of acting when p >= alpha."""
    act = p >= alpha
    hits = int(np.sum(act & o))
    misses = int(np.sum(~act & o))
    fa = int(np.sum(act & ~o))
    cn = int(np.sum(~act & ~o))
    base = o.mean()
    value = None
    denom = min(alpha, base) - alpha * base
    if hits + misses and fa + cn and denom > 0:
        H, F = hits / (hits + misses), fa / (fa + cn)
        value = (min(alpha, base) - F * alpha * (1 - base) + H * base * (1 - alpha) - base) / denom
        value = round(float(value), 3)
    return {"value": value, "hits": hits, "misses": misses, "false_alarms": fa}


def summary(ledger: Ledger) -> dict:
    entries = ledger.entries()
    pairs = [(f, o) for e in entries if e.get("kind") == "hindcast"
             for f, o in zip(e["forecasts"], e["outcomes"])]
    out = {
        "n_entries": len(entries),
        "n_alerts": sum(e.get("kind") == "alert" for e in entries),
        "n_scored": len(pairs),
        "chain_valid": ledger.verify(),
        "brier_score": None,
        "brier_skill_score": None,
        "reliability": [],
        "relative_value": {},
    }
    if not pairs:
        out["status"] = "Nothing scored yet: no observations or hindcasts in the ledger."
        return out

    p = np.array([x[0] for x in pairs], float)
    o = np.array([x[1] for x in pairs], bool)
    bs = float(np.mean((p - o) ** 2))
    base = o.mean()
    bs_clim = float(base * (1 - base))
    out["brier_score"] = round(bs, 4)
    out["brier_skill_score"] = round(1 - bs / bs_clim, 4) if bs_clim > 0 else None

    edges = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(p, edges) - 1, 0, 9)
    out["reliability"] = [
        {"predicted": round(float(p[idx == b].mean()), 3),
         "observed": round(float(o[idx == b].mean()), 3),
         "n": int((idx == b).sum())}
        for b in range(10) if (idx == b).any()
    ]
    out["relative_value"] = {uc.name: relative_value(p, o, uc.p_star) for uc in USER_CLASSES}
    out["status"] = (
        "Scored against synthetic nature runs (a perfect-model twin experiment). "
        "This checks calibration and the scoring code; it is not skill against real "
        "observations, which are not ingested yet."
        + ("" if out["chain_valid"] else " WARNING: hash chain broken; the ledger was edited.")
    )
    return out
