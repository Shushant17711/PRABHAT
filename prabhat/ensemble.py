"""S0: the input ensemble.

The problem statement's input is NCMRWF's NEPS-G ensemble. That data is not
in this repository, so this module generates a synthetic ensemble with the
same structure: N members on a ~12 km grid at 6-hourly leads, plus one extra
"nature run" drawn from the same distribution as the members. The nature run
stands in for what actually happened when the S8 ledger scores forecasts.

Members differ the way real ensemble members do. Position error grows with
lead time, intensity varies between members, and each field carries
power-law "weather texture", so the S4 downscaler has real spectrum to fit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cases import CaseSpec
from .geo import KM_PER_DEG, axis, haversine_km
from .spectral import powerlaw_noise


def soft_floor(x, scale: float = 2.0):
    """Smooth max(x, 0): accumulations cannot be negative, and a hard clip
    would leave kinks that read as fine-scale power downstream."""
    return scale * np.logaddexp(0.0, x / scale)


COARSE_RES = 0.12  # degrees, about 12-13 km: the NEPS-G grid spacing
LEADS = np.arange(0, 121, 6)  # hours
N_MEMBERS = 20
TEXTURE_BETA = 3.0  # 2-D spectral slope of the background texture


@dataclass
class Ensemble:
    spec: CaseSpec
    lat: np.ndarray
    lon: np.ndarray
    leads: np.ndarray
    members: np.ndarray  # (M, L, ny, nx) float32
    nature: np.ndarray  # (L, ny, nx) float32

    def exceed(self, field: np.ndarray) -> np.ndarray:
        return field > self.spec.threshold if self.spec.above else field < self.spec.threshold


def _interp_track(spec: CaseSpec, leads: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t = np.array([p[0] for p in spec.track], dtype=float)
    return (np.interp(leads, t, [p[1] for p in spec.track]),
            np.interp(leads, t, [p[2] for p in spec.track]))


def _interp_amp(spec: CaseSpec, leads: np.ndarray) -> np.ndarray:
    t = np.array([p[0] for p in spec.amplitude], dtype=float)
    return np.interp(leads, t, [p[1] for p in spec.amplitude])


def _member(spec, rng, LAT, LON, tlat, tlon, amp, leads) -> np.ndarray:
    # Each member gets one displacement direction. Its size grows linearly
    # with lead, which keeps the track smooth and lets spread grow over time.
    theta = rng.uniform(0, 2 * np.pi)
    err_km = np.abs(rng.normal(0.0, 1.0)) * spec.position_spread_km_per_day * leads / 24.0
    dlat = err_km * np.sin(theta) / KM_PER_DEG
    dlon = err_km * np.cos(theta) / (KM_PER_DEG * np.cos(np.radians(tlat)))
    amp_factor = max(0.3, 1.0 + rng.normal(0.0, spec.amplitude_spread))

    out = np.empty((len(leads),) + LAT.shape, dtype=np.float32)
    for i in range(len(leads)):
        d = haversine_km(LAT, LON, tlat[i] + dlat[i], tlon[i] + dlon[i])
        shape = np.exp(-0.5 * (d / spec.radius_km) ** 2)
        modulation = 1.0 + 0.2 * powerlaw_noise(LAT.shape, TEXTURE_BETA, rng)
        texture = spec.noise_sd * powerlaw_noise(LAT.shape, TEXTURE_BETA, rng)
        field = spec.background + spec.sign * amp[i] * amp_factor * shape * modulation + texture
        if spec.non_negative:
            field = soft_floor(field)
        out[i] = field
    return out


def generate(
    spec: CaseSpec,
    n_members: int = N_MEMBERS,
    seed: int | None = None,
    leads: np.ndarray | None = None,
) -> Ensemble:
    """Generate ``n_members`` members plus a nature run. Deterministic per seed."""
    rng = np.random.default_rng(spec.seed if seed is None else seed)
    leads = LEADS if leads is None else np.asarray(leads)
    lat_min, lon_min, lat_max, lon_max = spec.domain_bbox
    lat = axis(lat_min, lat_max, COARSE_RES)
    lon = axis(lon_min, lon_max, COARSE_RES)
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    tlat, tlon = _interp_track(spec, leads)
    amp = _interp_amp(spec, leads)

    runs = [_member(spec, rng, LAT, LON, tlat, tlon, amp, leads) for _ in range(n_members + 1)]
    return Ensemble(
        spec=spec, lat=lat, lon=lon, leads=leads,
        members=np.stack(runs[:-1]), nature=runs[-1],
    )
