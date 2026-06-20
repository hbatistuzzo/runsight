"""Tests for heat-adjusted pace metric."""

from runsight.metrics.heat_adjust import adjust_pace_for_heat, compute_heat_adjusted


def test_no_adjustment_below_reference():
    result = adjust_pace_for_heat(450, temp_c=18.0)
    assert result == 450  # No adjustment below 20°C


def test_adjustment_above_reference():
    result = adjust_pace_for_heat(450, temp_c=27.0, pct_per_degree=1.5)
    # 7°C above ref * 1.5%/°C = 10.5% penalty
    # adjusted = 450 / 1.105 ≈ 407
    assert result < 450
    assert result > 380


def test_hotter_means_bigger_adjustment():
    mild = adjust_pace_for_heat(450, temp_c=22.0, pct_per_degree=1.5)
    hot = adjust_pace_for_heat(450, temp_c=30.0, pct_per_degree=1.5)
    assert hot < mild  # Hotter day = bigger adjustment = faster adjusted pace


def test_compute_heat_adjusted(db):
    results = compute_heat_adjusted(db)
    assert len(results) == 3  # 3 activities with weather

    # Hot day (27.2°C) should have biggest adjustment
    hot_run = [r for r in results if r.temperature_c > 26][0]
    assert hot_run.adjustment_s > 0
    assert hot_run.adjusted_pace_s_km < hot_run.actual_pace_s_km
