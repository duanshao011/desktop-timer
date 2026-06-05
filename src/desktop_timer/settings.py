from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


APP_DIR_NAME = "desktop_timer"
SETTINGS_FILE_NAME = "settings.json"


@dataclass(frozen=True)
class Settings:
    daily_note_dir: Path | None = None


def default_settings_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME / SETTINGS_FILE_NAME
    return Path.home() / f".{APP_DIR_NAME}" / SETTINGS_FILE_NAME


def load_settings(settings_path: Path | None = None) -> Settings:
    path = settings_path or default_settings_path()
    if not path.exists():
        return Settings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Settings()

    daily_note_dir = data.get("daily_note_dir")
    if not daily_note_dir:
        return Settings()

    return Settings(daily_note_dir=Path(daily_note_dir))


def save_settings(settings: Settings, settings_path: Path | None = None) -> None:
    path = settings_path or default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "daily_note_dir": str(settings.daily_note_dir) if settings.daily_note_dir else None,
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
