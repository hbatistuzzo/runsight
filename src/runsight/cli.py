"""RunSight CLI — running analytics Garmin won't show you."""

from __future__ import annotations

import logging
import sys

import click

from runsight import __version__
from runsight.config import get_config_path, get_db_path, load_config, save_config
from runsight.db import Database


@click.group()
@click.version_option(__version__)
@click.option("--db", "db_path", default=None, help="Path to database file")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, db_path: str | None, verbose: bool) -> None:
    """RunSight — running analytics Garmin won't show you."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
    )
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path or str(get_db_path())


def get_db(ctx: click.Context) -> Database:
    return Database(ctx.obj["db_path"])


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize RunSight: create config and database."""
    config = load_config()

    if not config.get("garmin", {}).get("email"):
        email = click.prompt("Garmin Connect email")
        password = click.prompt("Garmin Connect password", hide_input=True)
        config["garmin"] = {"email": email, "password": password}

    if not config.get("athlete"):
        age = click.prompt("Your age", type=int)
        resting_hr = click.prompt("Resting heart rate (bpm, or 0 to auto-detect)", type=int, default=0)
        config["athlete"] = {"age": age}
        if resting_hr > 0:
            config["athlete"]["resting_hr"] = resting_hr

    save_config(config)
    click.echo(f"Config saved to {get_config_path()}")

    db = get_db(ctx)
    db.initialize()
    click.echo(f"Database created at {ctx.obj['db_path']}")


@cli.command()
@click.option("--days", default=30, help="How many days back to sync")
@click.pass_context
def sync(ctx: click.Context, days: int) -> None:
    """Sync activities from Garmin Connect."""
    from runsight.sync.garmin_api import GarminSync

    config = load_config()
    garmin = config.get("garmin", {})
    email = garmin.get("email")
    password = garmin.get("password")

    if not email or not password:
        click.echo("No Garmin credentials found. Run 'runsight init' first.")
        sys.exit(1)

    db = get_db(ctx)
    db.initialize()

    click.echo(f"Syncing last {days} days from Garmin Connect...")
    syncer = GarminSync(email, password, db)
    try:
        count = syncer.sync(days)
        click.echo(f"Synced {count} new activities.")
    except Exception as e:
        click.echo(f"Sync failed: {e}", err=True)
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.argument("date", required=False)
@click.pass_context
def pace(ctx: click.Context, date: str | None) -> None:
    """Show walk-filtered pace for a run (or all runs with walk data)."""
    from runsight.metrics.walk_filter import compute_all_walk_filtered, compute_walk_filtered_pace

    db = get_db(ctx)

    if date:
        row = db.query_one("SELECT id FROM activities WHERE date = ?", (date,))
        if not row:
            click.echo(f"No activity found for {date}")
            return
        result = compute_walk_filtered_pace(db, row["id"])
        if not result:
            return
        if not result.has_walk_data:
            click.echo(f"{date}: No walk data available. Blended pace: {result.blended_str}/km")
            click.echo("(This run has no typed splits — it may be all running)")
            return

        click.echo(f"\n  Walk-Filtered Pace — {date}")
        click.echo(f"  {'-' * 40}")
        click.echo(f"  Garmin shows:     {result.blended_str}/km  (blended)")
        click.echo(f"  You actually ran: {result.running_str}/km  ← your REAL pace")
        if result.walking_pace_s_km:
            click.echo(f"  Walking pace:     {result.walking_str}/km")
        click.echo(f"  Walk percentage:  {result.walk_pct}%")
        if result.pace_gap_s_km and result.pace_gap_s_km > 0:
            click.echo(f"  Walking dragged your average down by {int(result.pace_gap_s_km)}s/km")
        click.echo()
    else:
        results = compute_all_walk_filtered(db)
        if not results:
            click.echo("No activities with walk data found.")
            return

        click.echo(f"\n  {'Date':<12} {'Garmin':>8} {'Real':>8} {'Walk%':>6} {'Gap':>6}")
        click.echo(f"  {'-' * 44}")
        for r in results:
            gap = f"+{int(r.pace_gap_s_km)}s" if r.pace_gap_s_km and r.pace_gap_s_km > 0 else "—"
            click.echo(f"  {r.date:<12} {r.blended_str:>7} {r.running_str:>7} {r.walk_pct:>5.0f}% {gap:>5}")
        click.echo()

    db.close()


@cli.command()
@click.pass_context
def heat(ctx: click.Context) -> None:
    """Show heat-adjusted pace for all runs."""
    from runsight.metrics.heat_adjust import calibrate_heat_penalty, compute_heat_adjusted

    db = get_db(ctx)
    pct = calibrate_heat_penalty(db)
    results = compute_heat_adjusted(db)

    if not results:
        click.echo("No runs with weather data found.")
        db.close()
        return

    click.echo(f"\n  Heat-Adjusted Pace (ref: 20°C, penalty: {pct}%/°C)")
    click.echo(f"  {'-' * 58}")
    click.echo(f"  {'Date':<12} {'Actual':>8} {'@20°C':>8} {'Temp':>6} {'Saved':>6} {'HR':>4}")
    click.echo(f"  {'-' * 58}")

    for r in results:
        saved = f"-{int(r.adjustment_s)}s" if r.adjustment_s > 0 else "—"
        click.echo(
            f"  {r.date:<12} {r.actual_str:>7} {r.adjusted_str:>7} "
            f"{r.temperature_c:>4.0f}°C {saved:>5} {r.avg_hr:>4}"
        )
    click.echo()
    db.close()


@cli.command()
@click.option("--age", type=int, help="Your age (for 220-age comparison)")
@click.option("--resting-hr", type=int, help="Resting heart rate")
@click.option("--max-hr", type=int, help="Known max HR (overrides auto-detection)")
@click.pass_context
def zones(ctx: click.Context, age: int | None, resting_hr: int | None, max_hr: int | None) -> None:
    """Calculate your HR zones using the Karvonen method."""
    from runsight.metrics.zones import compare_with_formula, compute_zones

    db = get_db(ctx)
    config = load_config()
    athlete = config.get("athlete", {})

    age = age or athlete.get("age")
    resting_hr = resting_hr or athlete.get("resting_hr", 60)

    try:
        z = compute_zones(max_hr=max_hr, resting_hr=resting_hr, age=age, db=db)
    except ValueError as e:
        click.echo(f"Error: {e}")
        db.close()
        return

    click.echo("\n  HR Zones — Karvonen Method")
    click.echo(f"  {'-' * 40}")
    click.echo(f"  Max HR:     {z.max_hr} bpm ({z.max_hr_source})")
    click.echo(f"  Resting HR: {z.resting_hr} bpm")
    click.echo(f"  HRR:        {z.hrr} bpm")
    click.echo()
    for i, ((low, high), name) in enumerate(zip(z.zone_boundaries, z.zone_names)):
        click.echo(f"  Zone {i+1} ({name:12s}): {low:>3} – {high:>3} bpm")

    if age:
        cmp = compare_with_formula(age, z.max_hr)
        if cmp["difference"] != 0:
            click.echo(f"\n  WARNING: 220-age formula says your max HR is {cmp['formula_max_hr']} "
                       f"(off by {cmp['difference']:+d} bpm)")
            click.echo(f"    Formula Zone 2 ceiling: {cmp['formula_z2_ceiling']} bpm")
            click.echo(f"    Karvonen Zone 2 ceiling: {cmp['karvonen_z2_ceiling']} bpm")
            click.echo(f"    Your easy runs were {abs(cmp['z2_error_bpm'])} bpm harder than you thought!")
    click.echo()
    db.close()


@cli.command()
@click.pass_context
def milestones(ctx: click.Context) -> None:
    """Show your running milestones and achievements."""
    from runsight.metrics.milestones import detect_milestones

    db = get_db(ctx)
    ms = detect_milestones(db)

    if not ms:
        click.echo("No milestones detected. Sync some activities first!")
        db.close()
        return

    click.echo(f"\n  Running Milestones ({len(ms)} achievements)")
    click.echo(f"  {'-' * 55}")
    for m in ms:
        click.echo(f"  {m.date}  {m.name}")
        click.echo(f"             {m.value}")
    click.echo()
    db.close()


@cli.command()
@click.option("-o", "--output", default="runsight_report.html", help="Output HTML file path")
@click.pass_context
def report(ctx: click.Context, output: str) -> None:
    """Generate an HTML progress report with charts."""
    from pathlib import Path

    from runsight.reports.html import generate_report

    db = get_db(ctx)
    config = load_config()
    out = generate_report(db, Path(output), config.get("athlete"))
    click.echo(f"Report generated: {out.resolve()}")
    db.close()


@cli.command()
@click.pass_context
def summary(ctx: click.Context) -> None:
    """Quick summary of your running data."""
    db = get_db(ctx)

    total = db.query_one("SELECT count(*) as n FROM activities")
    if not total or total["n"] == 0:
        click.echo("No activities found. Run 'runsight sync' first.")
        db.close()
        return

    stats = db.query_one("""
        SELECT count(*) as runs,
               round(sum(distance_m)/1000, 1) as total_km,
               round(avg(avg_hr), 0) as avg_hr,
               min(date) as first_run,
               max(date) as last_run
        FROM activities
        WHERE distance_m > 500
    """)

    click.echo("\n  RunSight Summary")
    click.echo(f"  {'-' * 35}")
    click.echo(f"  Runs:       {stats['runs']}")
    click.echo(f"  Total:      {stats['total_km']} km")
    click.echo(f"  Avg HR:     {stats['avg_hr']} bpm")
    click.echo(f"  First run:  {stats['first_run']}")
    click.echo(f"  Last run:   {stats['last_run']}")
    click.echo()
    db.close()
