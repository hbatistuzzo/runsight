"""Shared test fixtures."""

import pytest

from runsight.db import Database


@pytest.fixture
def db(tmp_path):
    """Create an in-memory database with sample data."""
    db = Database(tmp_path / "test.db")
    db.initialize()

    # Insert sample activities
    db.upsert_activity(
        id=1, date="2026-06-15", start_time="2026-06-15 22:06:04",
        name="Night run", distance_m=6207, duration_s=2797,
        avg_pace_s_km=450.7, avg_hr=168, max_hr=182,
        weather_temp_c=21.1, time_of_day="night",
    )
    db.upsert_activity(
        id=2, date="2026-06-20", start_time="2026-06-20 14:48:16",
        name="Hot day run", distance_m=4613, duration_s=2272,
        avg_pace_s_km=492.5, avg_hr=176, max_hr=190,
        weather_temp_c=27.2, time_of_day="afternoon",
    )
    db.upsert_activity(
        id=3, date="2026-06-09", start_time="2026-06-09 18:30:18",
        name="Easy run", distance_m=5507, duration_s=2579,
        avg_pace_s_km=468.3, avg_hr=166, max_hr=180,
        weather_temp_c=25.0, time_of_day="evening",
    )

    # Typed splits for activity 2 (has walk breaks)
    db.upsert_typed_split(activity_id=2, split_index=0, type="RUN",
                          distance_m=3241, duration_s=1454, avg_hr=180, max_hr=190,
                          avg_speed_mps=2.229, avg_cadence=154)
    db.upsert_typed_split(activity_id=2, split_index=1, type="WALK",
                          distance_m=186, duration_s=166, avg_hr=158, max_hr=183,
                          avg_speed_mps=1.12, avg_cadence=98)
    db.upsert_typed_split(activity_id=2, split_index=2, type="RUN",
                          distance_m=479, duration_s=222, avg_hr=175, max_hr=184,
                          avg_speed_mps=2.158, avg_cadence=156)
    db.upsert_typed_split(activity_id=2, split_index=3, type="WALK",
                          distance_m=104, duration_s=87, avg_hr=171, max_hr=183,
                          avg_speed_mps=1.196, avg_cadence=105)
    db.upsert_typed_split(activity_id=2, split_index=4, type="RUN",
                          distance_m=125, duration_s=53, avg_hr=170, max_hr=179,
                          avg_speed_mps=2.35, avg_cadence=156)
    db.upsert_typed_split(activity_id=2, split_index=5, type="WALK",
                          distance_m=127, duration_s=105, avg_hr=165, max_hr=177,
                          avg_speed_mps=1.207, avg_cadence=105)
    db.upsert_typed_split(activity_id=2, split_index=6, type="RUN",
                          distance_m=231, duration_s=97, avg_hr=172, max_hr=184,
                          avg_speed_mps=2.382, avg_cadence=152)
    db.upsert_typed_split(activity_id=2, split_index=7, type="WALK",
                          distance_m=107, duration_s=88, avg_hr=173, max_hr=184,
                          avg_speed_mps=1.219, avg_cadence=103)

    # Typed splits for activity 3 (all running, no walks)
    db.upsert_typed_split(activity_id=3, split_index=0, type="RUN",
                          distance_m=5500, duration_s=2572, avg_hr=166, max_hr=180,
                          avg_speed_mps=2.139, avg_cadence=152)

    # Km splits
    db.upsert_km_split(activity_id=2, km=1, distance_m=1000, duration_s=430,
                       pace_s_km=430.0, avg_hr=170, max_hr=181)
    db.upsert_km_split(activity_id=2, km=2, distance_m=1000, duration_s=460,
                       pace_s_km=460.0, avg_hr=180, max_hr=185)
    db.upsert_km_split(activity_id=2, km=3, distance_m=1000, duration_s=435,
                       pace_s_km=435.0, avg_hr=186, max_hr=190)
    db.upsert_km_split(activity_id=2, km=4, distance_m=1000, duration_s=584,
                       pace_s_km=584.0, avg_hr=172, max_hr=187)

    db.commit()
    yield db
    db.close()
