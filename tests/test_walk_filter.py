"""Tests for walk-filtered pace metric."""

from runsight.metrics.walk_filter import compute_all_walk_filtered, compute_walk_filtered_pace


def test_walk_filtered_with_walk_breaks(db):
    result = compute_walk_filtered_pace(db, activity_id=2)
    assert result is not None
    assert result.has_walk_data
    assert result.running_pace_s_km is not None
    # Running pace should be faster than blended
    assert result.running_pace_s_km < result.blended_pace_s_km
    # Walking distance should be positive
    assert result.walking_distance_m > 0
    assert result.walk_pct > 0


def test_walk_filtered_all_running(db):
    result = compute_walk_filtered_pace(db, activity_id=3)
    assert result is not None
    assert result.has_walk_data
    # With no walk segments, running pace ≈ blended pace
    assert result.walking_distance_m == 0
    assert result.walk_pct == 0


def test_walk_filtered_no_typed_splits(db):
    result = compute_walk_filtered_pace(db, activity_id=1)
    assert result is not None
    assert not result.has_walk_data
    assert result.running_pace_s_km is None


def test_walk_filtered_nonexistent(db):
    result = compute_walk_filtered_pace(db, activity_id=999)
    assert result is None


def test_compute_all(db):
    results = compute_all_walk_filtered(db)
    assert len(results) >= 1
    for r in results:
        assert r.has_walk_data
