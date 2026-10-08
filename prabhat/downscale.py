"""S4: downscale each member from the ~12 km ensemble grid to 5 km.

Interpolation alone gives a field that is too smooth. That is the "spectral
smoothing" failure the problem statement names: the extremes get averaged
away. This module interpolates and then adds back the scales the coarse grid
cannot hold. It fits the power-law slope of the resolved spectrum, extrapolates
it past the coarse Nyquist wavenumber, and fills those scales with
random-phase detail at the extrapolated power. The approach follows RainFARM
(Rebora et al., 2006). It is a statistical downscaler, not a learned one; the
README explains where a trained model would plug in.

When the tube is too small to fit a slope, the downscaler falls back to plain
interpolation and says so. The S5 gate then catches the smoothing and the case
is published at coarse resolution only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .cases import CaseSpec
from .ensemble import COARSE_RES, soft_floor
from .geo import axis
from .spectral import _window, fit_power_law, radial_spectrum, shaped_detail

FINE_RES = 0.05  # degrees, about 5 km
K_CUT = 0.5 * FINE_RES / COARSE_RES  # coarse Nyquist, in fine-grid cycles per cell
ENVELOPE_MARGIN = 0.5  # degrees added around the tube before downscaling


def fit_band(shape: tuple[int, int]) -> tuple[float, float]:
    """The resolved wavenumbers a slope is fitted on.

    The band starts above the domain scale and stops at 0.6 x K_CUT, where
    interpolation starts to damp the spectrum.
    """
    return 3.0 / min(shape), 0.6 * K_CUT


def fine_axes(envelope, domain_bbox) -> tuple[np.ndarray, np.ndarray]:
    lat_min, lon_min, lat_max, lon_max = envelope
    d = domain_bbox
    lat_min = max(lat_min - ENVELOPE_MARGIN, d[0])
    lon_min = max(lon_min - ENVELOPE_MARGIN, d[1])
    lat_max = min(lat_max + ENVELOPE_MARGIN, d[2])
    lon_max = min(lon_max + ENVELOPE_MARGIN, d[3])
    return axis(lat_min, lat_max, FINE_RES), axis(lon_min, lon_max, FINE_RES)


def interpolate(field, lat_c, lon_c, lat_f, lon_f) -> np.ndarray:
    """Cubic-spline interpolation of a regular coarse grid onto a finer one.

    A cubic spline is used rather than bilinear because bilinear leaves a
    kink at every coarse cell edge. The spectrum reads those kinks as
    fine-scale power, which would hide the very smoothing the S5 gate looks for.
    """
    fy = (lat_f - lat_c[0]) / (lat_c[1] - lat_c[0])
    fx = (lon_f - lon_c[0]) / (lon_c[1] - lon_c[0])
    FY, FX = np.meshgrid(fy, fx, indexing="ij")
    return ndimage.map_coordinates(np.asarray(field, float), [FY, FX], order=3, mode="nearest")


class NotFittable(ValueError):
    """The fine domain is too small to resolve enough wavenumbers for a slope."""


@dataclass
class Downscaler:
    spec: CaseSpec
    method: str = "spectral"  # "spectral" or "interp"

    def __call__(self, coarse, lat_c, lon_c, lat_f, lon_f, rng) -> np.ndarray:
        interp = interpolate(coarse, lat_c, lon_c, lat_f, lon_f)
        if self.method == "interp":
            return interp
        k, power = radial_spectrum(interp)
        fit = fit_power_law(k, power, *fit_band(interp.shape))
        if fit is None:
            raise NotFittable(f"{interp.shape} grid resolves too few wavenumbers")
        a, b, _ = fit
        # The fit was measured through a Hann window, which removes a fixed
        # fraction of the power. The injected detail is unwindowed, so put that
        # fraction back.
        a -= np.log10(np.mean(_window(interp.shape) ** 2))
        fine = interp + shaped_detail(interp.shape, a, b, K_CUT, rng)
        if self.spec.non_negative:
            fine = soft_floor(fine)
        return fine
