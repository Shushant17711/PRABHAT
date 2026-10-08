"""S5: runtime gates that decide whether the 5 km field may be published.

The argument of the project: a generative downscaler will sometimes produce a
plausible-looking field it cannot stand behind, so every run is checked before
anything leaves the system.

G1, spectral fidelity. Smoothing shows up as missing small-scale power. The
gate fits a power law on the resolved part of the 5 km field, extrapolates
it, and compares it with the power the field actually has at the scales the
coarse grid could not see. A score of 1.0 means the extrapolation matched
exactly; a smoothed field scores near 0.

G2, cross-scale consistency. The 5 km exceedance region, averaged back to
12 km, must overlap the ensemble's own region (IoU) and sit near it
(centroid distance). Downscaling may add detail, but it must not move or
invent the extreme.

    both pass         -> PASS      publish at 5 km
    G1 fails          -> DEGRADE   coarse probabilities only, low confidence
    G2 fails          -> SUPPRESS  nothing published at 5 km
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .downscale import K_CUT, fit_band
from .geo import haversine_km
from .spectral import fit_power_law, radial_spectrum

SFS_MIN = 0.70
IOU_MIN = 0.40
CENTROID_MAX_KM = 50.0
P_REGION = 0.30  # probability contour the two scales are compared on


def spectral_fidelity(field: np.ndarray) -> float:
    k, power = radial_spectrum(field)
    fit = fit_power_law(k, power, *fit_band(field.shape))
    if fit is None:
        return float("nan")
    a, b, _ = fit
    sel = (k >= 1.2 * K_CUT) & (k <= 0.45) & (power > 0)
    if not sel.any():
        return float("nan")
    expected = 10 ** (a + b * np.log10(k[sel]))
    ratio = 10 ** np.mean(np.log10(power[sel] / expected))
    return float(min(ratio, 1.0 / ratio))


def _centroid(prob, mask, lat, lon):
    w = prob * mask
    if w.sum() == 0:
        return None
    return ((w.sum(axis=1) * lat).sum() / w.sum(), (w.sum(axis=0) * lon).sum() / w.sum())


def cross_scale(coarse_prob, lat_c, lon_c, fine_prob, lat_f, lon_f) -> tuple[float, float]:
    """Return (IoU, centroid distance in km) at the P_REGION contour."""
    # Average the 5 km field onto the 12 km cells it falls in.
    iy = np.abs(lat_c[None, :] - lat_f[:, None]).argmin(axis=1)
    ix = np.abs(lon_c[None, :] - lon_f[:, None]).argmin(axis=1)
    ys, xs = np.unique(iy), np.unique(ix)
    agg = np.zeros((len(ys), len(xs)))
    cnt = np.zeros_like(agg)
    ry = np.searchsorted(ys, iy)
    rx = np.searchsorted(xs, ix)
    np.add.at(agg, (ry[:, None], rx[None, :]), fine_prob)
    np.add.at(cnt, (ry[:, None], rx[None, :]), 1)
    agg /= cnt
    coarse = coarse_prob[np.ix_(ys, xs)]

    a, b = coarse >= P_REGION, agg >= P_REGION
    union = (a | b).sum()
    iou = float((a & b).sum() / union) if union else 1.0
    ca = _centroid(coarse, a, lat_c[ys], lon_c[xs])
    cb = _centroid(fine_prob, fine_prob >= P_REGION, lat_f, lon_f)
    if ca is None and cb is None:
        dist = 0.0
    elif ca is None or cb is None:
        dist = float("inf")
    else:
        dist = float(haversine_km(ca[0], ca[1], cb[0], cb[1]))
    return iou, dist


@dataclass
class GateResult:
    verdict: str
    reason: str
    spectral_fidelity: float
    spectral_pass: bool
    cross_scale_iou: float
    cross_scale_centroid_km: float
    cross_scale_pass: bool
    peak_lead_hour: int
    downscaler: str
    thresholds: dict

    def to_dict(self) -> dict:
        d = asdict(self)
        # The dashboard formats these as numbers. A score that could not be
        # measured is a failing score (0), and a missing region is "far away".
        d["spectral_fidelity"] = round(float(np.nan_to_num(self.spectral_fidelity, nan=0.0)), 3)
        d["cross_scale_iou"] = round(float(self.cross_scale_iou), 3)
        d["cross_scale_centroid_km"] = round(
            float(np.nan_to_num(self.cross_scale_centroid_km, posinf=9999.0, nan=9999.0)), 1)
        return d


def decide(sfs: float, iou: float, dist_km: float, peak_lead: int, downscaler: str) -> GateResult:
    spectral_pass = bool(np.isfinite(sfs) and sfs >= SFS_MIN)
    cross_pass = bool(iou >= IOU_MIN and dist_km <= CENTROID_MAX_KM)
    if not cross_pass:
        verdict = "SUPPRESS"
        reason = (f"The 5 km field disagrees with the ensemble it came from "
                  f"(IoU {iou:.2f}, centroid {dist_km:.0f} km apart): it has moved or "
                  f"invented the extreme, so nothing is published at 5 km.")
    elif not spectral_pass:
        verdict = "DEGRADE"
        reason = (f"The 5 km field is too smooth (SFS {sfs:.2f} < {SFS_MIN:.2f}), which "
                  f"would attenuate the extreme. Coarse probabilities are published instead.")
    else:
        verdict = "PASS"
        reason = (f"The 5 km field keeps the ensemble's fine-scale variance (SFS {sfs:.2f}) "
                  f"and its footprint (IoU {iou:.2f}, centroid {dist_km:.0f} km).")
    return GateResult(
        verdict=verdict, reason=reason,
        spectral_fidelity=sfs, spectral_pass=spectral_pass,
        cross_scale_iou=iou, cross_scale_centroid_km=dist_km, cross_scale_pass=cross_pass,
        peak_lead_hour=int(peak_lead), downscaler=downscaler,
        thresholds={"sfs_min": SFS_MIN, "iou_min": IOU_MIN, "centroid_max_km": CENTROID_MAX_KM},
    )
