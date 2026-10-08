"""S1: Extreme Forecast Index (Lalaurette, 2003).

    EFI = (2 / pi) * integral_0^1 (p - F_f(p)) / sqrt(p (1 - p)) dp

Here ``F_f(p)`` is the fraction of ensemble members below the climate's
p-quantile. EFI is +1 when every member is above the whole climate, -1 when
every member is below it, and 0 when the ensemble looks like climatology.

The problem statement asks for a 30-year ERA5 baseline. That is not on disk,
so the climate here is a normal distribution N(background, clim_sd) per case.
API responses carry ``is_synthetic_baseline: true`` to say so.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from .ensemble import Ensemble

# Substituting p = sin^2(t) turns dp / sqrt(p (1 - p)) into 2 dt, which removes
# the singularities at both ends, so a plain midpoint rule in t is accurate.
_T = (np.arange(200) + 0.5) / 200 * (np.pi / 2)
_P = np.sin(_T) ** 2


def efi(members: np.ndarray, clim_mean, clim_sd) -> np.ndarray:
    """EFI of an ensemble ``(M, ...)`` against a normal climatology."""
    q = norm.ppf(_P) * clim_sd + clim_mean  # (P,)
    flat = members.reshape(members.shape[0], -1)  # (M, cells)
    # F_f(p) per node and cell: fraction of members at or below the quantile.
    ff = (flat[None, :, :] <= q[:, None, None]).mean(axis=1)  # (P, cells)
    # (2 / pi) * integral of 2 dt over (0, pi/2) is 2 * the mean over the nodes.
    val = 2.0 * np.mean(_P[:, None] - ff, axis=0)
    return np.clip(val, -1, 1).reshape(members.shape[1:])


def efi_field(ens: Ensemble, stride: int = 2) -> dict:
    """EFI for every lead on a thinned grid (every ``stride``-th coarse cell)."""
    spec = ens.spec
    sub = ens.members[:, :, ::stride, ::stride]
    values = np.stack([efi(sub[:, li], spec.background, spec.clim_sd)
                       for li in range(sub.shape[1])])
    return {
        "lat": ens.lat[::stride].round(3).tolist(),
        "lon": ens.lon[::stride].round(3).tolist(),
        "lead_hours": [int(x) for x in ens.leads],
        "values": np.round(values, 3).tolist(),
        "is_synthetic_baseline": True,
        "baseline": f"simulated N({spec.background:g}, {spec.clim_sd:g}) {spec.units}",
    }
