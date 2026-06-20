"""Heat-adjusted pace — normalize your performance for temperature.

Problem: A runner doing 7:00/km at 21°C and 7:40/km at 27°C looks like they got
slower. In reality, heat raises HR by 10-15 bpm at the same effort, forcing a
slower pace. Without temperature normalization, hot-weather runs look like setbacks.

Solution: Build a simple model of pace vs temperature at similar HR, then show
what your pace "would have been" at a reference temperature (default 20°C).

Method: For each run, compute a heat penalty using the relationship between
temperature and cardiac drift. Research suggests ~1.5-3% pace penalty per °C
above ~15°C for recreational runners. We calibrate from your actual data.
"""

from __future__ import annotations

from dataclasses import dataclass

from runsight.db import Database

REFERENCE_TEMP_C = 20.0
DEFAULT_PCT_PER_DEGREE = 1.5  # percent pace penalty per °C above reference


@dataclass
class HeatAdjustedRun:
    activity_id: int
    date: str
    actual_pace_s_km: float
    adjusted_pace_s_km: float
    temperature_c: float
    avg_hr: int
    adjustment_s: float
    adjustment_pct: float

    def format_pace(self, pace_s: float) -> str:
        mins = int(pace_s) // 60
        secs = int(pace_s) % 60
        return f"{mins}:{secs:02d}"

    @property
    def actual_str(self) -> str:
        return self.format_pace(self.actual_pace_s_km)

    @property
    def adjusted_str(self) -> str:
        return self.format_pace(self.adjusted_pace_s_km)


def calibrate_heat_penalty(db: Database) -> float:
    """Estimate pace penalty per °C from the user's own data.

    Compares runs at different temperatures but similar HR to find
    the relationship. Falls back to the literature default if not
    enough data.
    """
    rows = db.query("""
        SELECT avg_pace_s_km, weather_temp_c, avg_hr
        FROM activities
        WHERE weather_temp_c IS NOT NULL
          AND avg_hr IS NOT NULL
          AND distance_m > 2000
          AND avg_pace_s_km > 0
        ORDER BY date
    """)

    if len(rows) < 6:
        return DEFAULT_PCT_PER_DEGREE

    temps = [r["weather_temp_c"] for r in rows]
    paces = [r["avg_pace_s_km"] for r in rows]
    hrs = [r["avg_hr"] for r in rows]

    n = len(rows)

    # Simple linear regression: pace = a + b * temp
    # Only using runs with HR within ±10 of median to control for effort
    sorted_hrs = sorted(hrs)
    median_hr = sorted_hrs[n // 2]
    filtered = [(t, p) for t, p, h in zip(temps, paces, hrs) if abs(h - median_hr) <= 12]

    if len(filtered) < 4:
        return DEFAULT_PCT_PER_DEGREE

    ft = [x[0] for x in filtered]
    fp = [x[1] for x in filtered]
    n2 = len(filtered)
    mt = sum(ft) / n2
    mp = sum(fp) / n2

    numerator = sum((t - mt) * (p - mp) for t, p in zip(ft, fp))
    denominator = sum((t - mt) ** 2 for t in ft)

    if denominator == 0:
        return DEFAULT_PCT_PER_DEGREE

    slope = numerator / denominator  # seconds per km per °C
    pct_per_degree = (slope / mp) * 100

    # Sanity check: should be between 0.5% and 4% per degree
    if 0.5 <= pct_per_degree <= 4.0:
        return round(pct_per_degree, 2)

    return DEFAULT_PCT_PER_DEGREE


def adjust_pace_for_heat(
    pace_s_km: float,
    temp_c: float,
    pct_per_degree: float = DEFAULT_PCT_PER_DEGREE,
    reference_temp: float = REFERENCE_TEMP_C,
) -> float:
    """Adjust a pace to what it would be at the reference temperature."""
    if temp_c <= reference_temp:
        return pace_s_km

    delta = temp_c - reference_temp
    penalty_pct = delta * pct_per_degree / 100.0
    return round(pace_s_km / (1 + penalty_pct), 1)


def compute_heat_adjusted(db: Database) -> list[HeatAdjustedRun]:
    pct = calibrate_heat_penalty(db)

    rows = db.query("""
        SELECT id, date, avg_pace_s_km, weather_temp_c, avg_hr
        FROM activities
        WHERE weather_temp_c IS NOT NULL
          AND avg_pace_s_km > 0
          AND distance_m > 2000
        ORDER BY date
    """)

    results = []
    for r in rows:
        actual = r["avg_pace_s_km"]
        temp = r["weather_temp_c"]
        adjusted = adjust_pace_for_heat(actual, temp, pct)
        adj_s = actual - adjusted
        adj_pct = (adj_s / actual * 100) if actual > 0 else 0

        results.append(HeatAdjustedRun(
            activity_id=r["id"],
            date=r["date"],
            actual_pace_s_km=actual,
            adjusted_pace_s_km=adjusted,
            temperature_c=temp,
            avg_hr=r["avg_hr"],
            adjustment_s=round(adj_s, 1),
            adjustment_pct=round(adj_pct, 1),
        ))

    return results
