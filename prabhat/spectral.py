"""Radially averaged power spectra, power-law fits and power-law noise.

Both the S4 downscaler and the S5 spectral-fidelity gate use these helpers.
The gate checks exactly the property the downscaler claims to keep, so the two
must measure a spectrum the same way.

Wavenumbers are in cycles per grid cell: Nyquist is 0.5, and a feature
spanning ``L`` cells sits at ``k = 1 / L``.
"""

from __future__ import annotations

import numpy as np


def _kgrid(shape: tuple[int, int]) -> np.ndarray:
    fy = np.fft.fftfreq(shape[0])
    fx = np.fft.fftfreq(shape[1])
    return np.hypot(fy[:, None], fx[None, :])


def _bins(shape: tuple[int, int]) -> np.ndarray:
    # One bin per resolvable step along the shorter axis.
    step = 1.0 / min(shape)
    return np.arange(step / 2, 0.5 + step, step)


def _window(shape: tuple[int, int]) -> np.ndarray:
    # A Hann taper removes the jump between opposite edges. Without it the
    # FFT reads that jump as small-scale power (a k^-2 artefact) and every
    # field would look like it had fine-scale detail.
    return np.outer(np.hanning(shape[0]), np.hanning(shape[1]))


def radial_spectrum(field: np.ndarray, windowed: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Return (k, power): total power in each annulus of wavenumber."""
    f = np.asarray(field, dtype=float)
    f = f - f.mean()
    if windowed:
        f = f * _window(f.shape)
    power2d = np.abs(np.fft.fft2(f)) ** 2 / f.size**2
    k = _kgrid(f.shape)
    edges = _bins(f.shape)
    idx = np.digitize(k.ravel(), edges)
    centres = 0.5 * (edges[:-1] + edges[1:])
    sums = np.bincount(idx, weights=power2d.ravel(), minlength=len(edges) + 1)
    power = sums[1 : len(edges)]
    return centres, power


def fit_power_law(k: np.ndarray, power: np.ndarray, k_lo: float, k_hi: float):
    """Least-squares fit of log10(power) = a + b * log10(k) over [k_lo, k_hi].

    Returns ``(a, b, n_points)``, or ``None`` with fewer than 4 usable bins:
    a slope fitted through three points is noise, not a spectrum.
    """
    sel = (k >= k_lo) & (k <= k_hi) & (power > 0)
    if sel.sum() < 4:
        return None
    b, a = np.polyfit(np.log10(k[sel]), np.log10(power[sel]), 1)
    return float(a), float(b), int(sel.sum())


def powerlaw_noise(shape: tuple[int, int], beta: float, rng: np.random.Generator) -> np.ndarray:
    """Zero-mean, unit-variance noise whose 2-D power falls off as k^-beta."""
    k = _kgrid(shape)
    k[0, 0] = np.inf
    spec = np.fft.fft2(rng.standard_normal(shape)) * k ** (-beta / 2)
    out = np.real(np.fft.ifft2(spec))
    sd = out.std()
    return out / sd if sd > 0 else out


def shaped_detail(
    shape: tuple[int, int],
    a: float,
    b: float,
    k_cut: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Random-phase field carrying only wavenumbers above ``k_cut``.

    Its radial spectrum follows ``10**a * k**b`` in the same units as
    :func:`radial_spectrum` (unwindowed). The scaling depends only on |k|, so
    it is Hermitian-symmetric and the inverse transform stays real.
    """
    spec = np.fft.fft2(rng.standard_normal(shape))
    edges = _bins(shape)
    idx = np.digitize(_kgrid(shape), edges)
    centres = np.concatenate([[np.nan], 0.5 * (edges[:-1] + edges[1:]), [np.nan]])
    n = shape[0] * shape[1]
    have = np.bincount(idx.ravel(), weights=(np.abs(spec) ** 2).ravel() / n**2,
                       minlength=len(centres))
    with np.errstate(divide="ignore", invalid="ignore"):
        want = np.where(centres > k_cut, 10**a * centres**b, 0.0)
        gain = np.sqrt(np.where(have > 0, want / have, 0.0))
    gain = np.nan_to_num(gain)
    return np.real(np.fft.ifft2(spec * gain[idx]))
