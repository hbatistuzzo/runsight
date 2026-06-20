"""User configuration management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path.home() / ".runsight"
DEFAULT_DB_NAME = "runsight.db"
CONFIG_FILE = "config.json"


def get_config_dir() -> Path:
    d = DEFAULT_CONFIG_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_db_path() -> Path:
    return get_config_dir() / DEFAULT_DB_NAME


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_config(config: dict[str, Any]) -> None:
    path = get_config_path()
    path.write_text(json.dumps(config, indent=2))


def get_garmin_credentials() -> tuple[str, str] | None:
    config = load_config()
    garmin = config.get("garmin", {})
    email = garmin.get("email")
    password = garmin.get("password")
    if email and password:
        return email, password
    return None
