from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class TaskRecord:
    started_at: datetime
    duration: timedelta
    task: str


class DailyNoteMissingError(FileNotFoundError):
    """Raised when the expected daily note file does not exist."""


def daily_note_path(daily_note_dir: Path, day: date | None = None) -> Path:
    target_day = day or date.today()
    return daily_note_dir / f"{target_day:%Y-%m-%d}.md"


def format_duration(duration: timedelta) -> str:
    total_seconds = max(0, int(duration.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分")
    if seconds or not parts:
        parts.append(f"{seconds}秒")
    return "".join(parts)


def format_record(record: TaskRecord) -> str:
    started = record.started_at.strftime("%H:%M")
    duration = format_duration(record.duration)
    task = " ".join(record.task.split())
    return f"- {started}｜用时 {duration}｜{task}"


def append_record(daily_note_dir: Path, record: TaskRecord) -> Path:
    note_path = daily_note_path(daily_note_dir, record.started_at.date())
    if not note_path.exists():
        raise DailyNoteMissingError(str(note_path))
    if not note_path.is_file():
        raise DailyNoteMissingError(str(note_path))

    existing = note_path.read_text(encoding="utf-8")
    line = format_record(record)
    prefix = "" if not existing or existing.endswith(("\n", "\r")) else "\n"
    note_path.write_text(f"{existing}{prefix}{line}\n", encoding="utf-8")
    return note_path
