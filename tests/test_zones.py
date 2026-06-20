"""Tests for Karvonen HR zone calculator."""

import pytest

from runsight.metrics.zones import compare_with_formula, compute_zones


def test_karvonen_zones_explicit():
    z = compute_zones(max_hr=199, resting_hr=53)
    assert z.hrr == 146
    assert z.max_hr == 199
    assert len(z.zone_boundaries) == 5
    # Zone 2 should be around 140-155 for HRR=146, RHR=53
    z2_low, z2_high = z.zone_boundaries[1]
    assert 120 < z2_low < 145
    assert 145 < z2_high < 160


def test_auto_detect_max_hr(db):
    z = compute_zones(resting_hr=60, db=db)
    # Max HR from fixture data is 190
    assert z.max_hr == 190
    assert "observed" in z.max_hr_source


def test_fallback_to_age():
    z = compute_zones(age=38, resting_hr=60)
    assert z.max_hr == 182
    assert "220-age" in z.max_hr_source


def test_no_data_raises():
    with pytest.raises(ValueError):
        compute_zones()


def test_compare_with_formula():
    cmp = compare_with_formula(age=38, actual_max=199)
    assert cmp["formula_max_hr"] == 182
    assert cmp["difference"] == 17
    assert cmp["z2_error_bpm"] > 0
