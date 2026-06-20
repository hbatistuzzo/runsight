"""SQLite database schema and operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    name TEXT,
    distance_m REAL,
    duration_s REAL,
    avg_pace_s_km REAL,
    avg_hr INTEGER,
    max_hr INTEGER,
    calories INTEGER,
    avg_cadence REAL,
    elevation_gain_m REAL,
    weather_temp_c REAL,
    weather_humidity_pct INTEGER,
    weather_wind_mps REAL,
    time_of_day TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS km_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    km INTEGER NOT NULL,
    distance_m REAL,
    duration_s REAL,
    pace_s_km REAL,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_cadence REAL,
    elevation_gain_m REAL,
    FOREIGN KEY (activity_id) REFERENCES activities(id),
    UNIQUE(activity_id, km)
);

CREATE TABLE IF NOT EXISTS typed_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    split_index INTEGER NOT NULL,
    type TEXT NOT NULL,
    distance_m REAL,
    duration_s REAL,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_speed_mps REAL,
    avg_cadence REAL,
    FOREIGN KEY (activity_id) REFERENCES activities(id),
    UNIQUE(activity_id, split_index)
);

CREATE TABLE IF NOT EXISTS body_comp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    weight_kg REAL,
    bmi REAL,
    fat_pct REAL,
    muscle_mass_pct REAL,
    visceral_fat_rating REAL
);

CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date);
CREATE INDEX IF NOT EXISTS idx_km_splits_activity ON km_splits(activity_id);
CREATE INDEX IF NOT EXISTS idx_typed_splits_activity ON typed_splits(activity_id);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def upsert_activity(self, **kwargs: Any) -> None:
        cols = list(kwargs.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO activities ({col_names}) VALUES ({placeholders})",
            list(kwargs.values()),
        )

    def upsert_km_split(self, **kwargs: Any) -> None:
        cols = list(kwargs.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO km_splits ({col_names}) VALUES ({placeholders})",
            list(kwargs.values()),
        )

    def upsert_typed_split(self, **kwargs: Any) -> None:
        cols = list(kwargs.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO typed_splits ({col_names}) VALUES ({placeholders})",
            list(kwargs.values()),
        )

    def commit(self) -> None:
        self.conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def activity_exists(self, activity_id: int) -> bool:
        row = self.query_one("SELECT 1 FROM activities WHERE id = ?", (activity_id,))
        return row is not None

    def latest_activity_date(self) -> str | None:
        row = self.query_one("SELECT max(date) as d FROM activities")
        return row["d"] if row else None
