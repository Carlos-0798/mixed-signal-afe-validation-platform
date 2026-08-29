import pytest

from dashboard.measurements.dc_sweep import analyze_dc_sweep, exclude_saturated, linear_fit
from dashboard.models import SweepPoint


def test_exact_linear_fit() -> None:
    points = [SweepPoint(x, 2.5 * x + 12.0) for x in (100, 200, 300, 400)]
    result = linear_fit(points)
    assert result.gain == pytest.approx(2.5)
    assert result.offset_mv == pytest.approx(12.0)
    assert result.r_squared == pytest.approx(1.0)


def test_noisy_fit_remains_close() -> None:
    noise = (-2, 1, 0, 2, -1)
    points = [SweepPoint(x, 2.0 * x + 10 + e) for x, e in zip((100, 200, 300, 400, 500), noise)]
    result = linear_fit(points)
    assert result.gain == pytest.approx(2.0, abs=0.01)
    assert result.r_squared > 0.999


def test_saturation_bands_are_excluded() -> None:
    points = [
        SweepPoint(0, 25),
        SweepPoint(100, 210),
        SweepPoint(200, 410),
        SweepPoint(300, 610),
        SweepPoint(2000, 3275),
    ]
    kept, excluded = exclude_saturated(points, low_output_mv=25, high_output_mv=3275)
    assert [point.input_mv for point in kept] == [100, 200, 300]
    assert len(excluded) == 2
    result = analyze_dc_sweep(points, low_output_mv=25, high_output_mv=3275)
    assert result.gain == pytest.approx(2.0)
    assert result.offset_mv == pytest.approx(10.0)
    assert result.excluded_points == 2


def test_insufficient_linear_points_raise() -> None:
    points = [SweepPoint(0, 25), SweepPoint(100, 200), SweepPoint(2000, 3275)]
    with pytest.raises(ValueError, match="at least two"):
        analyze_dc_sweep(points, low_output_mv=25, high_output_mv=3275)


def test_constant_input_is_not_fittable() -> None:
    with pytest.raises(ValueError, match="must not all be equal"):
        linear_fit([SweepPoint(1, 2), SweepPoint(1, 3)])

