"""Demo cases: one per hazard the problem statement names.

Each case describes a synthetic event: a track, how strong the anomaly is at
each lead, and how uncertain the ensemble is about both. The numbers are
chosen to look like plausible Indian events. They are not reanalyses of real
storms; see the README section on data.
"""

from __future__ import annotations

from dataclasses import dataclass

# (lead_hour, lat, lon)
Track = tuple[tuple[float, float, float], ...]
# (lead_hour, anomaly magnitude in the variable's units)
Profile = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class CaseSpec:
    id: str
    hazard: str  # cyclone | extreme_rain | heatwave | coldwave
    title: str
    init_time: str  # ISO 8601, UTC
    domain_bbox: tuple[float, float, float, float]  # lat_min, lon_min, lat_max, lon_max
    variable: str
    units: str
    background: float  # climatological mean of the variable in the domain
    clim_sd: float  # climatological spread, used by the simulated EFI baseline
    noise_sd: float  # amplitude of weather "texture" unrelated to the event
    threshold: float
    above: bool  # True: hazard is variable > threshold; False: variable < threshold
    impact_field: str  # name of the exceedance field responders see
    track: Track
    amplitude: Profile
    radius_km: float
    position_spread_km_per_day: float
    amplitude_spread: float  # relative member-to-member spread of the anomaly
    seed: int
    non_negative: bool = False  # accumulations cannot go below zero

    @property
    def sign(self) -> float:
        return 1.0 if self.above else -1.0


CASES: tuple[CaseSpec, ...] = (
    CaseSpec(
        id="bay_of_bengal_cyclone",
        hazard="cyclone",
        title="Severe cyclonic storm recurving towards the Odisha coast",
        init_time="2026-05-18T00:00:00Z",
        domain_bbox=(10.0, 80.0, 24.0, 94.0),
        variable="wind_speed_10m",
        units="kt",
        background=14.0,
        clim_sd=9.0,
        noise_sd=3.0,
        threshold=62.0,
        above=True,
        impact_field="p_wind_gt_62kt",
        track=((0, 13.0, 88.5), (24, 14.8, 87.6), (48, 16.6, 86.9),
               (72, 18.4, 86.3), (96, 19.8, 85.9), (120, 21.5, 86.6)),
        amplitude=((0, 38), (36, 62), (72, 92), (96, 95), (108, 80), (120, 48)),
        radius_km=75.0,
        position_spread_km_per_day=70.0,
        amplitude_spread=0.14,
        seed=2605,
    ),
    CaseSpec(
        id="konkan_extreme_rain",
        hazard="extreme_rain",
        title="Offshore trough driving extreme rainfall over the Konkan coast",
        init_time="2026-07-24T00:00:00Z",
        domain_bbox=(15.0, 69.0, 23.0, 77.0),
        variable="precip_12h",
        units="mm/12 h",
        background=6.0,
        clim_sd=22.0,
        noise_sd=3.5,
        threshold=100.0,
        above=True,
        impact_field="p_rain_100mm_12h",
        track=((0, 18.4, 72.2), (48, 18.8, 72.6), (96, 19.3, 73.0), (120, 19.5, 73.2)),
        amplitude=((0, 0), (18, 45), (42, 135), (66, 150), (90, 95), (120, 30)),
        radius_km=55.0,
        position_spread_km_per_day=45.0,
        amplitude_spread=0.22,
        seed=2607,
        non_negative=True,
    ),
    CaseSpec(
        id="rajasthan_heatwave",
        hazard="heatwave",
        title="Pre-monsoon heat wave building over west Rajasthan",
        init_time="2026-05-26T00:00:00Z",
        domain_bbox=(21.0, 67.0, 33.0, 80.0),
        variable="t2m_max",
        units="°C",
        background=38.0,
        clim_sd=2.6,
        noise_sd=0.6,
        threshold=45.0,
        above=True,
        impact_field="p_t2m_gt_45c",
        track=((0, 26.4, 71.8), (48, 26.9, 72.9), (96, 27.6, 74.3), (120, 28.0, 75.0)),
        amplitude=((0, 3.0), (48, 6.5), (84, 9.0), (120, 7.5)),
        radius_km=230.0,
        position_spread_km_per_day=60.0,
        amplitude_spread=0.12,
        seed=2605_26,
    ),
    CaseSpec(
        id="punjab_coldwave",
        hazard="coldwave",
        title="Cold wave spreading south-east across Punjab and Haryana",
        init_time="2026-12-28T00:00:00Z",
        domain_bbox=(24.0, 70.0, 35.0, 82.0),
        variable="t2m_min",
        units="°C",
        background=9.0,
        clim_sd=2.2,
        noise_sd=0.5,
        threshold=4.0,
        above=False,
        impact_field="p_t2m_lt_4c",
        track=((0, 31.6, 74.4), (60, 30.6, 75.9), (120, 29.6, 77.4)),
        amplitude=((0, 2.0), (36, 5.5), (72, 7.0), (120, 6.0)),
        radius_km=210.0,
        position_spread_km_per_day=55.0,
        amplitude_spread=0.13,
        seed=2612,
    ),
)

CASES_BY_ID = {c.id: c for c in CASES}
