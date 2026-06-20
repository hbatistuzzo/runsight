# RunSight 🏃

**Running analytics Garmin won't show you.**

![GitHub top language](https://img.shields.io/github/languages/top/hbatistuzzo/runsight)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/hbatistuzzo/runsight)
![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/hbatistuzzo/runsight)
![GitHub last commit](https://img.shields.io/github/last-commit/hbatistuzzo/runsight)

---

## Project Context

This started as a personal project to understand my own running data better. I'm a data scientist / data engineer by trade (oceanography background, long story, check my [profile](https://github.com/hbatistuzzo)), and I was frustrated that Garmin collects all this great data but only shows you the basics.

The whole thing was built with [Claude Code](https://claude.ai/claude-code) using the [Garmin MCP server](https://github.com/Taxuspt/garmin_mcp) for data acquisition. The database was populated through AI-assisted API calls rather than manual CSV exports. If you're curious about MCP (Model Context Protocol) in practice, this is a concrete example of what it looks like when an AI agent interacts with real-world APIs.

---

## Why does this exist?

I started running at 38. The first few weeks were brutal, mostly walking with some running in between, which is perfectly fine and exactly how it should be done. But Garmin Connect didn't see it that way. It just lumped everything together and told me my average pace was **8:12/km**. Depressing.

Then I looked closer. Garmin *does* record which segments are running and which are walking (they call them "typed splits"). It just... doesn't use that information to separate the paces. When I did the math myself, my *actual running pace* was **7:28/km**. Walking intervals were dragging the average down by **44 seconds per km**. That's a completely different picture of where my fitness actually is.

Then came the heat. I live in Niterói, Brazil 🇧🇷, where a "cool day" in summer means 27°C with 80% humidity. My "worst" runs were always on hot days. Same effort, same heart rate, but the pace looked terrible. Without temperature normalization, every summer run looked like a regression. Garmin records the temperature for every activity. It just doesn't do anything useful with it.

And the HR zones? Garmin used the `220 - age` formula, giving me a max HR of **182**. My actual max HR turned out to be **199**, a full **17 bpm higher**. Every run I thought was "easy" was actually a threshold run. I was overtraining without knowing it. The `220 - age` formula is a population average from the 1970s, and it can be off by ±10-20 bpm for any individual. Your entire training plan can be wrong because of this single assumption.

> Garmin records all the data you need to fix these problems. It just doesn't show you the answers.

RunSight does.

---

## Technologies

- Python 3.10+
- Click (CLI framework)
- SQLite (local storage, no cloud, no account, no tracking)
- Jinja2 + Chart.js (HTML reports with interactive charts)
- garminconnect (Garmin API sync)

---

## Features

### 🔹 Walk-Filtered Pace

If you use run/walk intervals (as many beginners should! Jeff Galloway has built an entire coaching method around this), Garmin's blended average makes you look slower than you are. RunSight separates the typed splits and shows your real running pace.

```
$ runsight pace 2026-06-20

  Walk-Filtered Pace — 2026-06-20
  ────────────────────────────────────────
  Garmin shows:     8:12/km  (blended)
  You actually ran: 7:28/km  ← your REAL pace
  Walking pace:     13:52/km
  Walk percentage:  11%
  Walking dragged your average down by 44s/km
```

**Insight:** this is not a vanity metric. If you're training by pace (e.g. "I want to run a sub-35:00 5K"), you need to know your *running* pace, not the blended average that includes the 2 minutes you spent walking to bring your heart rate down. That blended number is useless for goal-setting.

---

### 🔹 Heat-Adjusted Pace

Running at 27°C is physiologically harder than at 20°C. Your body diverts blood to the skin for cooling, cardiac output drops, heart rate rises by 10-15 bpm at the same pace. This is well-documented in exercise physiology but Garmin doesn't account for it.

RunSight uses a linear regression with HR control to calibrate the penalty (default ~1.5%/°C above 20°C), then shows what your pace *would have been* at a reference temperature:

```
$ runsight heat

  Heat-Adjusted Pace (ref: 20°C, penalty: 1.5%/°C)
  ──────────────────────────────────────────────────────────
  Date         Actual    @20°C   Temp   Saved   HR
  ──────────────────────────────────────────────────────────
  2026-06-15   7:30/km  7:30/km   21°C     —   168
  2026-06-20   8:12/km  7:24/km   27°C   -48s  176
```

**Insight:** that "bad" 8:12 run on a 27°C day? Equivalent to 7:24 at 20°C, actually *faster* than the 7:30 run two days earlier. Without this normalization, you'd think you got worse. You didn't. It was just hot.

---

### 🔹 Karvonen HR Zones

The `220 - age` formula is the bane of beginner runners. It's a population-level average that can be off by 10-20 bpm for any individual. RunSight auto-detects your *actual* max HR from your activity history and calculates zones using the **Karvonen method** (Heart Rate Reserve), which is significantly more accurate because it accounts for both max HR *and* resting HR.

```
$ runsight zones --age 38

  HR Zones — Karvonen Method
  ────────────────────────────────────────
  Max HR:     199 bpm (observed in activity data)
  Resting HR: 53 bpm
  HRR:        146 bpm

  Zone 1 (Recovery    ):  126 – 141 bpm
  Zone 2 (Easy/Aerobic):  141 – 155 bpm
  Zone 3 (Tempo       ):  155 – 170 bpm
  Zone 4 (Threshold   ):  170 – 184 bpm
  Zone 5 (VO2max      ):  184 – 199 bpm

  ⚠ 220-age formula says your max HR is 182 (off by +17 bpm)
    → Your easy runs were 15 bpm harder than you thought!
```

**Insight:** with the formula, Zone 2 ceiling is 130 bpm. With Karvonen using real data, it's 155 bpm. That means runs at 145 bpm that *felt* easy (and *were* easy) showed up as "Zone 4" on the Garmin dashboard, making you think you were overtraining when you were actually perfectly fine. The anxiety this causes beginners is real.

---

### 🔹 Beginner Milestones

Garmin gives you badges for... buying Garmin products. Meanwhile, your first continuous 5K, your first sub-7:00/km split, your longest run ever, your first week of 3+ runs: none of that gets acknowledged. RunSight detects these milestones from your activity history:

```
$ runsight milestones

  Running Milestones (18 achievements)
  -------------------------------------------------------
  2026-04-29  First 1K ...
  2026-04-30  First 5K
  2026-05-10  First Sub-7:30/km Run
  2026-05-22  First Sub-7:00/km Run
  2026-05-31  Fastest 1K Split — 5:49/km
  2026-06-03  First 10K
  ...
```

---

### 🔹 HTML Progress Report

Generates a self-contained HTML report with interactive Chart.js visualizations: weekly volume, heat-adjusted pace trends, km1 progression (dual-axis with HR). Dark theme. No server needed, just open the file in a browser.

```
$ runsight report -o my_progress.html
```

---

## Installation

```bash
pip install runsight
```

## Quick Start

```bash
# 1. Initialize (saves Garmin credentials + creates database)
runsight init

# 2. Sync your recent runs
runsight sync --days 90

# 3. See your real pace
runsight pace

# 4. Check your zones
runsight zones --age 38 --resting-hr 53

# 5. Generate a full report
runsight report
```

---

## Data Sources

RunSight supports two ways to get your Garmin data:

- **Direct API** (default): Uses the `garminconnect` Python library. Works standalone, just `pip install` and go.
- **MCP** (for AI agent users): If you're using [Claude Code](https://claude.ai/claude-code) or another MCP-compatible agent, RunSight can pull data via the [Garmin MCP server](https://github.com/Taxuspt/garmin_mcp). This is actually how I built this project: the entire database was bootstrapped through MCP calls to Garmin's API via Claude Code.

---

## How It Works

RunSight syncs your Garmin Connect data into a local SQLite database, then computes metrics that Garmin doesn't surface:

1. **Typed splits** → Walk-filtered pace (Garmin records RUN vs WALK segments but doesn't use them to separate pace)
2. **Weather data** → Heat-adjusted performance (Garmin records temperature but doesn't normalize pace for it)
3. **Historical max HR** → Proper Karvonen zones (instead of the inaccurate 220-age formula)
4. **Activity progression** → Milestone detection (distances, pace records, consistency)

All data stays local. No cloud, no account, no tracking. Your running data is yours.

> **Fun fact (aka bug report):** Garmin's API returns temperature in a field called `temperature_celsius`... except the values are actually in Fahrenheit 🤦. RunSight handles the conversion for you.

---

## License

MIT
