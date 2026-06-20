"""Generate static HTML progress reports with Chart.js visualizations."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from runsight.db import Database
from runsight.metrics.heat_adjust import calibrate_heat_penalty, compute_heat_adjusted
from runsight.metrics.milestones import detect_milestones
from runsight.metrics.walk_filter import compute_all_walk_filtered
from runsight.metrics.zones import compute_zones

TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_report(db: Database, output_path: Path, athlete_config: dict | None = None) -> Path:
    athlete_config = athlete_config or {}
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.globals["zip"] = zip
    template = env.get_template("report.html")

    # Gather all data
    activities = db.query("""
        SELECT date, name, round(distance_m/1000.0, 1) as km,
               avg_pace_s_km, avg_hr, max_hr, weather_temp_c, time_of_day
        FROM activities WHERE distance_m > 500 ORDER BY date
    """)

    weekly = db.query("""
        SELECT strftime('%Y-W%W', date) as week,
               count(*) as runs,
               round(sum(distance_m)/1000, 1) as km,
               round(avg(avg_hr), 0) as avg_hr
        FROM activities WHERE distance_m > 500
        GROUP BY week ORDER BY week
    """)

    km1_progression = db.query("""
        SELECT a.date, k.pace_s_km, k.avg_hr, a.weather_temp_c
        FROM km_splits k
        JOIN activities a ON k.activity_id = a.id
        WHERE k.km = 1 AND k.distance_m >= 950
        ORDER BY a.date
    """)

    heat_data = compute_heat_adjusted(db)
    heat_penalty = calibrate_heat_penalty(db)
    walk_data = compute_all_walk_filtered(db)
    milestone_data = detect_milestones(db)

    try:
        zone_data = compute_zones(
            resting_hr=athlete_config.get("resting_hr", 60),
            age=athlete_config.get("age"),
            db=db,
        )
    except ValueError:
        zone_data = None

    def fmt_pace(s):
        if not s or s <= 0:
            return "--:--"
        return f"{int(s)//60}:{int(s)%60:02d}"

    html = template.render(
        activities=[dict(r) for r in activities],
        weekly=[dict(r) for r in weekly],
        km1_progression=[dict(r) for r in km1_progression],
        heat_data=heat_data,
        heat_penalty=heat_penalty,
        walk_data=walk_data,
        milestones=milestone_data,
        zones=zone_data,
        fmt_pace=fmt_pace,
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path
