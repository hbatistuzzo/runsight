"""Sync Garmin data via the garminconnect Python library (direct API)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from garminconnect import Garmin

from runsight.db import Database

logger = logging.getLogger(__name__)


def fahrenheit_to_celsius(f: float) -> float:
    return round((f - 32) * 5.0 / 9.0, 1)


def classify_time_of_day(iso_time: str) -> str:
    try:
        hour = datetime.fromisoformat(iso_time).hour
    except (ValueError, TypeError):
        return "unknown"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    if hour < 20:
        return "evening"
    return "night"


class GarminSync:
    def __init__(self, email: str, password: str, db: Database):
        self.client = Garmin(email, password)
        self.db = db
        self._logged_in = False

    def login(self) -> None:
        if not self._logged_in:
            self.client.login()
            self._logged_in = True
            logger.info("Logged in to Garmin Connect")

    def sync(self, days: int = 30) -> int:
        self.login()
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=days)).isoformat()

        activities = self.client.get_activities_by_date(start, end, "running")
        synced = 0

        for act in activities:
            aid = act["activityId"]
            if self.db.activity_exists(aid):
                continue

            self._sync_activity(aid, act)
            synced += 1

        self.db.commit()
        logger.info("Synced %d new activities", synced)
        return synced

    def _sync_activity(self, aid: int, summary: dict) -> None:
        start_time = summary.get("startTimeLocal", "")
        distance = summary.get("distance", 0) or 0
        duration = summary.get("duration", 0) or 0
        pace = (duration / (distance / 1000.0)) if distance > 0 else 0

        self.db.upsert_activity(
            id=aid,
            date=start_time[:10] if start_time else "",
            start_time=start_time,
            name=summary.get("activityName", ""),
            distance_m=distance,
            duration_s=duration,
            avg_pace_s_km=round(pace, 1),
            avg_hr=summary.get("averageHR"),
            max_hr=summary.get("maxHR"),
            calories=summary.get("calories"),
            avg_cadence=summary.get("averageRunningCadenceInStepsPerMinute"),
            elevation_gain_m=summary.get("elevationGain"),
            time_of_day=classify_time_of_day(start_time),
        )

        self._sync_weather(aid)
        self._sync_splits(aid)
        self._sync_typed_splits(aid)

    def _sync_weather(self, aid: int) -> None:
        try:
            weather = self.client.get_activity_weather(aid)
            if weather:
                temp_raw = weather.get("temperature", weather.get("temperature_celsius"))
                temp_c = fahrenheit_to_celsius(temp_raw) if temp_raw and temp_raw > 50 else temp_raw
                self.db.conn.execute(
                    """UPDATE activities
                       SET weather_temp_c = ?, weather_humidity_pct = ?, weather_wind_mps = ?
                       WHERE id = ?""",
                    (temp_c, weather.get("humidity", weather.get("humidity_percent")),
                     weather.get("windSpeed", weather.get("wind_speed_mps")), aid),
                )
        except Exception as e:
            logger.warning("Could not fetch weather for %d: %s", aid, e)

    def _sync_splits(self, aid: int) -> None:
        try:
            data = self.client.get_activity_splits(aid)
            laps = data if isinstance(data, list) else data.get("laps", data.get("lapDTOs", []))
            km = 0
            for lap in laps:
                dist = lap.get("distance", lap.get("distance_meters", 0)) or 0
                dur = lap.get("duration", lap.get("duration_seconds", 0)) or 0
                if dist < 500:
                    continue
                km += 1
                pace = (dur / (dist / 1000.0)) if dist > 0 else 0
                self.db.upsert_km_split(
                    activity_id=aid,
                    km=km,
                    distance_m=dist,
                    duration_s=dur,
                    pace_s_km=round(pace, 1),
                    avg_hr=lap.get("averageHR", lap.get("avg_hr_bpm")),
                    max_hr=lap.get("maxHR", lap.get("max_hr_bpm")),
                    avg_cadence=lap.get("averageRunCadence", lap.get("avg_cadence")),
                    elevation_gain_m=lap.get("elevationGain", lap.get("elevation_gain_meters")),
                )
        except Exception as e:
            logger.warning("Could not fetch splits for %d: %s", aid, e)

    def _sync_typed_splits(self, aid: int) -> None:
        try:
            data = self.client.get_activity_typed_splits(aid)
            splits = data if isinstance(data, list) else data.get("typedSplits", [])
            for i, split in enumerate(splits):
                split_type = split.get("splitType", split.get("type", "UNKNOWN"))
                if split_type not in ("RWD_RUN", "RWD_WALK", "RUN", "WALK"):
                    continue
                norm_type = "RUN" if "RUN" in split_type else "WALK"
                self.db.upsert_typed_split(
                    activity_id=aid,
                    split_index=i,
                    type=norm_type,
                    distance_m=split.get("distance", split.get("distance_meters", 0)),
                    duration_s=split.get("duration", split.get("duration_seconds", 0)),
                    avg_hr=split.get("averageHR", split.get("avg_hr_bpm")),
                    max_hr=split.get("maxHR", split.get("max_hr_bpm")),
                    avg_speed_mps=split.get("averageSpeed", split.get("avg_speed_mps")),
                    avg_cadence=split.get("averageRunCadence", split.get("avg_cadence")),
                )
        except Exception as e:
            logger.warning("Could not fetch typed splits for %d: %s", aid, e)
