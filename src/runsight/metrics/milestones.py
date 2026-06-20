"""Beginner milestone detection — celebrate what Garmin ignores.

For new runners, "first continuous 5K" or "first hill without stopping" are
life-changing moments. Garmin shows pace and HR but never says "congratulations,
you just ran your longest distance ever." This module detects those milestones
automatically from activity history.
"""

from __future__ import annotations

from dataclasses import dataclass

from runsight.db import Database


@dataclass
class Milestone:
    name: str
    date: str
    activity_id: int
    value: str
    description: str

    def __str__(self) -> str:
        return f"[{self.date}] {self.name}: {self.value} — {self.description}"


def detect_milestones(db: Database) -> list[Milestone]:
    milestones = []
    milestones.extend(_distance_firsts(db))
    milestones.extend(_pace_records(db))
    milestones.extend(_longest_runs(db))
    milestones.extend(_consistency_streaks(db))
    milestones.sort(key=lambda m: m.date)
    return milestones


def _distance_firsts(db: Database) -> list[Milestone]:
    """Detect first time reaching distance thresholds."""
    thresholds = [
        (1000, "First 1K"),
        (2000, "First 2K"),
        (3000, "First 3K"),
        (4000, "First 4K"),
        (5000, "First 5K"),
        (6000, "First 6K"),
        (8000, "First 8K"),
        (10000, "First 10K"),
        (15000, "First 15K"),
        (21097, "First Half Marathon"),
    ]

    results = []
    for threshold, name in thresholds:
        row = db.query_one(
            """SELECT id, date, distance_m, duration_s
               FROM activities
               WHERE distance_m >= ?
               ORDER BY date
               LIMIT 1""",
            (threshold,),
        )
        if row:
            dist_km = row["distance_m"] / 1000
            dur_min = row["duration_s"] / 60
            results.append(Milestone(
                name=name,
                date=row["date"],
                activity_id=row["id"],
                value=f"{dist_km:.1f} km in {dur_min:.0f} min",
                description=f"First run of {threshold/1000:.0f}+ km",
            ))
    return results


def _pace_records(db: Database) -> list[Milestone]:
    """Detect personal best paces at each km split."""
    results = []

    # Fastest single km split
    row = db.query_one("""
        SELECT k.activity_id, a.date, k.km, k.pace_s_km, k.avg_hr
        FROM km_splits k
        JOIN activities a ON k.activity_id = a.id
        WHERE k.distance_m >= 950
        ORDER BY k.pace_s_km
        LIMIT 1
    """)
    if row:
        pace_min = int(row["pace_s_km"]) // 60
        pace_sec = int(row["pace_s_km"]) % 60
        results.append(Milestone(
            name="Fastest 1K Split",
            date=row["date"],
            activity_id=row["activity_id"],
            value=f"{pace_min}:{pace_sec:02d}/km (km {row['km']}, HR {row['avg_hr']})",
            description="Personal best single kilometer",
        ))

    # Sub-pace milestones
    pace_targets = [
        (480, "Sub-8:00/km"),
        (450, "Sub-7:30/km"),
        (420, "Sub-7:00/km"),
        (390, "Sub-6:30/km"),
        (360, "Sub-6:00/km"),
        (330, "Sub-5:30/km"),
        (300, "Sub-5:00/km"),
    ]
    for target_s, name in pace_targets:
        row = db.query_one(
            """SELECT a.id, a.date, a.avg_pace_s_km
               FROM activities a
               WHERE a.avg_pace_s_km <= ? AND a.avg_pace_s_km > 0 AND a.distance_m > 2000
               ORDER BY a.date
               LIMIT 1""",
            (target_s,),
        )
        if row:
            p = int(row["avg_pace_s_km"])
            results.append(Milestone(
                name=f"First {name} Run",
                date=row["date"],
                activity_id=row["id"],
                value=f"{p//60}:{p%60:02d}/km average",
                description=f"First run averaging under {name.replace('Sub-', '')}",
            ))

    return results


def _longest_runs(db: Database) -> list[Milestone]:
    """Track progressive longest run milestones."""
    rows = db.query(
        "SELECT id, date, distance_m, duration_s FROM activities ORDER BY date"
    )
    results = []
    max_dist = 0
    for row in rows:
        if row["distance_m"] > max_dist * 1.2 and row["distance_m"] > 2000:
            max_dist = row["distance_m"]
            km = max_dist / 1000
            results.append(Milestone(
                name="New Longest Run",
                date=row["date"],
                activity_id=row["id"],
                value=f"{km:.1f} km",
                description=f"Distance record: {km:.1f} km",
            ))
    return results


def _consistency_streaks(db: Database) -> list[Milestone]:
    """Detect weeks with 3+ runs (consistency milestones)."""
    rows = db.query("""
        SELECT strftime('%Y-W%W', date) as week, count(*) as runs, min(date) as first_date
        FROM activities
        WHERE distance_m > 1000
        GROUP BY week
        HAVING runs >= 3
        ORDER BY week
    """)

    results = []
    streak = 0
    for row in rows:
        streak += 1
        if streak in (1, 3, 5, 10, 20):
            label = f"{streak} Week{'s' if streak > 1 else ''} of 3+ Runs"
            results.append(Milestone(
                name=label,
                date=row["first_date"],
                activity_id=0,
                value=f"{row['runs']} runs this week",
                description=f"Maintained 3+ runs/week for {streak} {'consecutive ' if streak > 1 else ''}week{'s' if streak > 1 else ''}",
            ))

    return results
