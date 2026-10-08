"""S1: follow the anomaly through lead time as one object, an anomaly tube.

At each lead, the ensemble exceedance probability marks where the hazard may
occur. The largest connected region gives that lead's bounding box, centroid,
confidence and intensity. Consecutive leads make up the tube, which is the 4-D
bounding box the problem statement asks for.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
from scipy import ndimage

from .ensemble import COARSE_RES, Ensemble

P_DETECT = 0.10  # an anomaly is tracked once 2 of 20 members see it


@dataclass
class TubePoint:
    lead_hour: int
    centroid_lat: float
    centroid_lon: float
    bbox: list[float]  # [lat_min, lon_min, lat_max, lon_max]
    confidence: float  # fraction of members that exceed inside the box
    intensity: float  # ensemble median of each member's extreme inside the box


@dataclass
class Tube:
    tube_id: str
    case_id: str
    hazard: str
    variable: str
    units: str
    threshold: float
    points: list[TubePoint] = field(default_factory=list)

    @property
    def envelope(self) -> tuple[float, float, float, float]:
        """Union of every lead's bounding box."""
        b = np.array([p.bbox for p in self.points])
        return (b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max())

    def to_dict(self) -> dict:
        return asdict(self)


def track(ens: Ensemble, p_detect: float = P_DETECT) -> list[Tube]:
    spec = ens.spec
    exceed = ens.exceed(ens.members)  # (M, L, ny, nx) bool
    prob = exceed.mean(axis=0)
    points: list[TubePoint] = []

    for li, lead in enumerate(ens.leads):
        mask = prob[li] >= p_detect
        if not mask.any():
            if points:
                break  # the object has dissipated; a later blob is a new object
            continue
        labels, n = ndimage.label(mask)
        sizes = ndimage.sum_labels(prob[li], labels, index=range(1, n + 1))
        mask = labels == (int(np.argmax(sizes)) + 1)

        w = prob[li] * mask
        iy, ix = np.nonzero(mask)
        clat = float((w.sum(axis=1) * ens.lat).sum() / w.sum())
        clon = float((w.sum(axis=0) * ens.lon).sum() / w.sum())
        bbox = [
            round(float(ens.lat[iy.min()] - COARSE_RES), 3),
            round(float(ens.lon[ix.min()] - COARSE_RES), 3),
            round(float(ens.lat[iy.max()] + COARSE_RES), 3),
            round(float(ens.lon[ix.max()] + COARSE_RES), 3),
        ]
        inside = ens.members[:, li][:, mask]  # (M, cells)
        extreme = inside.max(axis=1) if spec.above else inside.min(axis=1)
        confidence = float(exceed[:, li][:, mask].any(axis=1).mean())
        points.append(TubePoint(
            lead_hour=int(lead),
            centroid_lat=round(clat, 3),
            centroid_lon=round(clon, 3),
            bbox=bbox,
            confidence=round(confidence, 3),
            intensity=round(float(np.median(extreme)), 2),
        ))

    if len(points) < 2:
        return []
    return [Tube(
        tube_id=f"{spec.id}-T1", case_id=spec.id, hazard=spec.hazard,
        variable=spec.variable, units=spec.units, threshold=spec.threshold,
        points=points,
    )]
