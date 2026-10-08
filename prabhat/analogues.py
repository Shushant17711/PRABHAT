"""S2: analogue retrieval. STUB.

The design calls for retrieving past events whose evolution resembles the
current tube, using a learned embedding over reanalysis. This stub has a
small hand-written catalogue of well-known Indian events and ranks those of
the same hazard by distance between the tube's peak and the event's location.
Run status reports it as a stub, and the dashboard badges it, so nobody takes
the similarity score for more than a distance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .geo import haversine_km
from .tracking import Tube


@dataclass(frozen=True)
class Event:
    event_id: str
    display_name: str
    hazard: str
    lat: float  # approximate location of the event's main impact
    lon: float
    analog_stage: str


CATALOGUE: tuple[Event, ...] = (
    Event("cyc-phailin-2013", "Cyclone Phailin (2013)", "cyclone", 19.3, 84.9, "landfall, south Odisha"),
    Event("cyc-hudhud-2014", "Cyclone Hudhud (2014)", "cyclone", 17.7, 83.3, "landfall, Visakhapatnam"),
    Event("cyc-fani-2019", "Cyclone Fani (2019)", "cyclone", 19.8, 85.8, "landfall, Puri"),
    Event("cyc-amphan-2020", "Cyclone Amphan (2020)", "cyclone", 21.6, 88.2, "landfall, Sundarbans"),
    Event("cyc-yaas-2021", "Cyclone Yaas (2021)", "cyclone", 21.4, 86.9, "landfall, north Odisha"),
    Event("cyc-biparjoy-2023", "Cyclone Biparjoy (2023)", "cyclone", 23.2, 68.6, "landfall, Kutch"),
    Event("rain-mumbai-2005", "Mumbai floods (July 2005)", "extreme_rain", 19.1, 72.9, "peak 24 h accumulation"),
    Event("rain-chennai-2015", "Chennai floods (Dec 2015)", "extreme_rain", 13.1, 80.3, "peak 24 h accumulation"),
    Event("rain-kerala-2018", "Kerala floods (Aug 2018)", "extreme_rain", 10.0, 76.5, "multi-day accumulation"),
    Event("rain-uttarakhand-2013", "Uttarakhand floods (June 2013)", "extreme_rain", 30.7, 79.0, "peak 24 h accumulation"),
    Event("heat-phalodi-2016", "Phalodi heat wave (May 2016)", "heatwave", 27.1, 72.4, "peak maximum temperature"),
    Event("heat-churu-2019", "Churu heat wave (June 2019)", "heatwave", 28.3, 75.0, "peak maximum temperature"),
    Event("heat-delhi-2024", "North India heat wave (May 2024)", "heatwave", 28.6, 77.2, "multi-day heat"),
    Event("cold-north-india-2019", "North India cold wave (Dec 2019)", "coldwave", 28.6, 77.2, "multi-day cold"),
)

SCALE_KM = 600.0  # e-folding distance of the similarity kernel


@dataclass
class Analogue:
    event_id: str
    display_name: str
    analog_stage: str
    similarity: float
    distance_km: float


def retrieve(tube: Tube, k: int = 3) -> list[dict]:
    peak = max(tube.points, key=lambda p: p.confidence)
    out = []
    for ev in CATALOGUE:
        if ev.hazard != tube.hazard:
            continue
        d = float(haversine_km(peak.centroid_lat, peak.centroid_lon, ev.lat, ev.lon))
        out.append(Analogue(ev.event_id, ev.display_name, ev.analog_stage,
                            round(float(np.exp(-d / SCALE_KM)), 3), round(d, 1)))
    out.sort(key=lambda a: -a.similarity)
    return [asdict(a) for a in out[:k]]
