import numpy as np
import pytest

from prabhat.alerts import USER_CLASSES, churn
from prabhat.cases import CASES, CASES_BY_ID
from prabhat.efi import efi
from prabhat.ensemble import generate
from prabhat.gates import decide, spectral_fidelity
from prabhat.pipeline import run_case
from prabhat.spectral import fit_power_law, powerlaw_noise, radial_spectrum
from prabhat.tracking import track


def test_powerlaw_noise_has_the_slope_it_was_asked_for():
    # beta is the 2-D slope; summing over an annulus of ~k cells adds +1.
    field = powerlaw_noise((256, 256), beta=3.0, rng=np.random.default_rng(0))
    k, p = radial_spectrum(field, windowed=False)
    _, slope, _ = fit_power_law(k, p, 0.02, 0.4)
    assert slope == pytest.approx(1 - 3.0, abs=0.2)


def test_efi_limits():
    clim_mean, clim_sd = np.array([0.0]), np.array([1.0])
    assert efi(np.full((20, 1), 10.0), clim_mean, clim_sd)[0] == pytest.approx(1.0, abs=0.02)
    assert efi(np.full((20, 1), -10.0), clim_mean, clim_sd)[0] == pytest.approx(-1.0, abs=0.02)
    climate_like = np.random.default_rng(0).standard_normal((2000, 1))
    assert abs(efi(climate_like, clim_mean, clim_sd)[0]) < 0.1


def test_ensemble_is_deterministic_per_seed():
    spec = CASES[0]
    a, b = generate(spec, seed=1), generate(spec, seed=1)
    assert np.array_equal(a.members, b.members)
    assert not np.array_equal(a.members, generate(spec, seed=2).members)


@pytest.mark.parametrize("spec", CASES, ids=lambda s: s.id)
def test_every_case_yields_a_tube(spec):
    tubes = track(generate(spec))
    assert tubes and len(tubes[0].points) >= 2
    lat_min, lon_min, lat_max, lon_max = spec.domain_bbox
    for p in tubes[0].points:
        assert lat_min <= p.centroid_lat <= lat_max
        assert lon_min <= p.centroid_lon <= lon_max


def test_accumulations_stay_non_negative():
    ens = generate(CASES_BY_ID["konkan_extreme_rain"])
    assert ens.members.min() >= 0


def test_gate_verdicts():
    assert decide(0.9, 0.8, 5.0, 0, "spectral").verdict == "PASS"
    assert decide(0.1, 0.8, 5.0, 0, "interp").verdict == "DEGRADE"
    assert decide(0.9, 0.1, 5.0, 0, "spectral").verdict == "SUPPRESS"
    assert decide(0.9, 0.8, 300.0, 0, "spectral").verdict == "SUPPRESS"


def test_gate_scores_a_smooth_field_low_and_a_textured_one_high():
    rng = np.random.default_rng(0)
    textured = powerlaw_noise((120, 120), 3.0, rng)
    from scipy.ndimage import gaussian_filter
    smooth = gaussian_filter(textured, 4)
    assert spectral_fidelity(textured) > 0.7
    assert spectral_fidelity(smooth) < 0.3


def test_spectral_downscaler_passes_and_interpolation_is_degraded():
    assert run_case("konkan_extreme_rain").gate["verdict"] == "PASS"
    control = run_case("konkan_interp_control")
    assert control.gate["verdict"] == "DEGRADE"
    assert control.raster["resolution_km"] == 12
    assert all(a["confidence_mode"] == "coarse" for a in control.alerts)


def test_hysteresis_cuts_churn_without_delaying_the_first_alert():
    spec = CASES_BY_ID["bay_of_bengal_cyclone"]
    peak = np.random.default_rng(0).uniform(0, 1, 500)
    for c in churn(spec, peak, n_members=20):
        assert c["churn_with"] < c["churn_without"]
        assert c["mean_delay_runs"] == 0
        assert c["lead_time_preserved"]


def test_alert_thresholds_follow_cost_loss():
    for uc in USER_CLASSES:
        assert uc.p_star == pytest.approx(uc.cost / uc.loss)
        assert uc.p_clear < uc.p_raise
