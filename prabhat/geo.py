"""Small geodesy helpers shared by every stage."""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0
KM_PER_DEG = np.pi * EARTH_RADIUS_KM / 180.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Broadcasts over numpy arrays."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def axis(lo: float, hi: float, res: float) -> np.ndarray:
    """Regular coordinate axis from lo to hi (inclusive) at the given step."""
    n = int(round((hi - lo) / res)) + 1
    return np.round(lo + res * np.arange(n), 6)
