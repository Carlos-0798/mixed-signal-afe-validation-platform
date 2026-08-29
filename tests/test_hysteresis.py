import pytest

from dashboard.measurements.hysteresis import calculate_hysteresis


def test_hysteresis_uses_transition_midpoints() -> None:
    rising = [(1700, 0), (1790, 0), (1810, 1), (1900, 1)]
    falling = [(1900, 1), (1510, 1), (1490, 0), (1400, 0)]
    result = calculate_hysteresis(rising, falling)
    assert result.threshold_high_mv == pytest.approx(1800)
    assert result.threshold_low_mv == pytest.approx(1500)
    assert result.width_mv == pytest.approx(300)


def test_missing_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="no 0->1"):
        calculate_hysteresis([(1000, 0), (2000, 0)], [(2000, 1), (1000, 0)])


def test_inverted_thresholds_are_rejected() -> None:
    rising = [(1000, 0), (1200, 1)]
    falling = [(2000, 1), (1800, 0)]
    with pytest.raises(ValueError, match="below"):
        calculate_hysteresis(rising, falling)

