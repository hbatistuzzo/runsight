"""Walk-filtered pace — your REAL running pace without walking segments dragging it down.

Problem: Beginner runners using run/walk intervals see a blended average pace that's
much slower than their actual running pace. A 7:28/km runner who walks 20% of the
distance shows as 8:12/km — discouraging and misleading.

Solution: Separate RUN and WALK typed splits from Garmin data to compute:
- Running-only pace (what you actually run at)
- Walking percentage (how much you walked)
- Pace gap (how much walking drags down your average)
"""

from __future__ import annotations

from dataclasses import dataclass

from runsight.db import Database


@dataclass
class WalkFilterResult:
    activity_id: int
    date: str
    blended_pace_s_km: float
    running_pace_s_km: float | None
    walking_pace_s_km: float | None
    running_distance_m: float
    walking_distance_m: float
    total_distance_m: float
    walk_pct: float
    pace_gap_s_km: float | None

    @property
    def has_walk_data(self) -> bool:
        return self.running_pace_s_km is not None

    def format_pace(self, pace_s: float | None) -> str:
        if pace_s is None:
            return "--:--"
        mins = int(pace_s) // 60
        secs = int(pace_s) % 60
        return f"{mins}:{secs:02d}"

    @property
    def blended_str(self) -> str:
        return self.format_pace(self.blended_pace_s_km)

    @property
    def running_str(self) -> str:
        return self.format_pace(self.running_pace_s_km)

    @property
    def walking_str(self) -> str:
        return self.format_pace(self.walking_pace_s_km)


def compute_walk_filtered_pace(db: Database, activity_id: int) -> WalkFilterResult | None:
    activity = db.query_one(
        "SELECT id, date, distance_m, duration_s, avg_pace_s_km FROM activities WHERE id = ?",
        (activity_id,),
    )
    if not activity:
        return None

    typed = db.query(
        "SELECT type, distance_m, duration_s FROM typed_splits WHERE activity_id = ? ORDER BY split_index",
        (activity_id,),
    )

    blended = activity["avg_pace_s_km"]
    total_dist = activity["distance_m"]

    if not typed:
        return WalkFilterResult(
            activity_id=activity_id,
            date=activity["date"],
            blended_pace_s_km=blended,
            running_pace_s_km=None,
            walking_pace_s_km=None,
            running_distance_m=total_dist,
            walking_distance_m=0,
            total_distance_m=total_dist,
            walk_pct=0,
            pace_gap_s_km=None,
        )

    run_dist = sum(r["distance_m"] for r in typed if r["type"] == "RUN")
    run_dur = sum(r["duration_s"] for r in typed if r["type"] == "RUN")
    walk_dist = sum(r["distance_m"] for r in typed if r["type"] == "WALK")
    walk_dur = sum(r["duration_s"] for r in typed if r["type"] == "WALK")

    run_pace = (run_dur / (run_dist / 1000.0)) if run_dist > 0 else None
    walk_pace = (walk_dur / (walk_dist / 1000.0)) if walk_dist > 0 else None
    walk_pct = (walk_dist / (run_dist + walk_dist) * 100) if (run_dist + walk_dist) > 0 else 0
    pace_gap = (blended - run_pace) if run_pace else None

    return WalkFilterResult(
        activity_id=activity_id,
        date=activity["date"],
        blended_pace_s_km=blended,
        running_pace_s_km=round(run_pace, 1) if run_pace else None,
        walking_pace_s_km=round(walk_pace, 1) if walk_pace else None,
        running_distance_m=run_dist,
        walking_distance_m=walk_dist,
        total_distance_m=total_dist,
        walk_pct=round(walk_pct, 1),
        pace_gap_s_km=round(pace_gap, 1) if pace_gap else None,
    )


def compute_all_walk_filtered(db: Database) -> list[WalkFilterResult]:
    activities = db.query(
        """SELECT DISTINCT a.id
           FROM activities a
           JOIN typed_splits ts ON ts.activity_id = a.id
           ORDER BY a.date"""
    )
    results = []
    for row in activities:
        result = compute_walk_filtered_pace(db, row["id"])
        if result and result.has_walk_data:
            results.append(result)
    return results
