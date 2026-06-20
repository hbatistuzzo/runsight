"""Karvonen HR zone calculator — proper zones from YOUR actual data.

Problem: Most runners set HR zones using the 220-age formula. For a 38-year-old,
that gives maxHR = 182. But actual max HR varies enormously — one user's real max
was 199 (17 bpm higher!). This puts Zone 2 boundaries off by 10+ bpm, meaning
"easy runs" are actually threshold runs.

Solution: Detect actual max HR from activity history, use resting HR from the
watch, and calculate zones using the Karvonen (Heart Rate Reserve) method, which
is more accurate than %maxHR for trained individuals.
"""

from __future__ import annotations

from dataclasses import dataclass

from runsight.db import Database


@dataclass
class HRZones:
    max_hr: int
    resting_hr: int
    hrr: int
    zone_boundaries: list[tuple[int, int]]
    zone_names: list[str]
    method: str
    max_hr_source: str

    def zone_for_hr(self, hr: int) -> int:
        for i, (low, high) in enumerate(self.zone_boundaries):
            if low <= hr <= high:
                return i + 1
        return 5 if hr > self.zone_boundaries[-1][1] else 1

    def format(self) -> str:
        lines = [
            f"Method: {self.method}",
            f"Max HR: {self.max_hr} bpm ({self.max_hr_source})",
            f"Resting HR: {self.resting_hr} bpm",
            f"Heart Rate Reserve: {self.hrr} bpm",
            "",
        ]
        for i, ((low, high), name) in enumerate(zip(self.zone_boundaries, self.zone_names)):
            lines.append(f"  Zone {i+1} ({name}): {low}-{high} bpm")
        return "\n".join(lines)


ZONE_NAMES = ["Recovery", "Easy/Aerobic", "Tempo", "Threshold", "VO2max"]
ZONE_FRACTIONS = [
    (0.50, 0.60),  # Zone 1
    (0.60, 0.70),  # Zone 2
    (0.70, 0.80),  # Zone 3
    (0.80, 0.90),  # Zone 4
    (0.90, 1.00),  # Zone 5
]


def detect_max_hr(db: Database) -> tuple[int, str]:
    """Find actual max HR from activity history."""
    row = db.query_one("SELECT max(max_hr) as peak FROM activities WHERE max_hr IS NOT NULL")
    if row and row["peak"]:
        return row["peak"], "observed in activity data"
    return 0, "no data"


def compute_zones(
    max_hr: int | None = None,
    resting_hr: int | None = None,
    age: int | None = None,
    db: Database | None = None,
) -> HRZones:
    """Calculate Karvonen HR zones.

    Priority for max_hr: explicit > detected from data > 220-age formula.
    """
    source = "manual"
    if max_hr is None and db is not None:
        max_hr, source = detect_max_hr(db)
    if max_hr is None or max_hr == 0:
        if age is not None:
            max_hr = 220 - age
            source = "220-age formula (less accurate)"
        else:
            raise ValueError("Need max_hr, activity data, or age to calculate zones")

    if resting_hr is None:
        resting_hr = 60  # reasonable default

    hrr = max_hr - resting_hr
    boundaries = []
    for low_frac, high_frac in ZONE_FRACTIONS:
        low = round(resting_hr + hrr * low_frac)
        high = round(resting_hr + hrr * high_frac)
        boundaries.append((low, high))

    return HRZones(
        max_hr=max_hr,
        resting_hr=resting_hr,
        hrr=hrr,
        zone_boundaries=boundaries,
        zone_names=ZONE_NAMES,
        method="Karvonen (Heart Rate Reserve)",
        max_hr_source=source,
    )


def compare_with_formula(age: int, actual_max: int) -> dict:
    """Show how wrong 220-age is for this person."""
    formula_max = 220 - age
    diff = actual_max - formula_max
    formula_z2_top = round(formula_max * 0.70)  # %maxHR Z2 ceiling
    karvonen_z2_top = round(60 + (actual_max - 60) * 0.70)  # Karvonen Z2 ceiling (assuming RHR 60)

    return {
        "formula_max_hr": formula_max,
        "actual_max_hr": actual_max,
        "difference": diff,
        "formula_z2_ceiling": formula_z2_top,
        "karvonen_z2_ceiling": karvonen_z2_top,
        "z2_error_bpm": karvonen_z2_top - formula_z2_top,
    }
