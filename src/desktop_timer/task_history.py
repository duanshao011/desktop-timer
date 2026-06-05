from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CompletedTask:
    started_at: datetime
    finished_at: datetime
    duration: timedelta
    name: str
    merge_count: int = 1


@dataclass
class RunningTask:
    name: str
    started_at: datetime
    state: str = "running"
    elapsed_before_run: float = 0.0
    run_started_monotonic: float | None = None

    def pause(self, now_monotonic: float | None = None) -> None:
        if self.state != "running":
            return
        if now_monotonic is None:
            now_monotonic = time.monotonic()
        if self.run_started_monotonic is not None:
            self.elapsed_before_run += now_monotonic - self.run_started_monotonic
        self.run_started_monotonic = None
        self.state = "paused"

    def resume(self, now_monotonic: float | None = None) -> None:
        if self.state != "paused":
            return
        if now_monotonic is None:
            now_monotonic = time.monotonic()
        self.run_started_monotonic = now_monotonic
        self.state = "running"

    def elapsed_seconds(self, now_monotonic: float | None = None) -> float:
        if self.state == "running" and self.run_started_monotonic is not None:
            if now_monotonic is None:
                now_monotonic = time.monotonic()
            return self.elapsed_before_run + (now_monotonic - self.run_started_monotonic)
        return self.elapsed_before_run


def merge_into_completed(
    completed: list[CompletedTask],
    finished: CompletedTask,
) -> None:
    name_key = finished.name.strip()
    existing_idx: int | None = None
    for i, c in enumerate(completed):
        if c.name.strip() == name_key:
            existing_idx = i
            break

    if existing_idx is None:
        completed.insert(0, finished)
        return

    existing = completed[existing_idx]
    merged = CompletedTask(
        started_at=min(existing.started_at, finished.started_at),
        finished_at=max(existing.finished_at, finished.finished_at),
        duration=existing.duration + finished.duration,
        name=existing.name,
        merge_count=existing.merge_count + finished.merge_count,
    )
    del completed[existing_idx]
    completed.insert(0, merged)


def format_duration(duration: timedelta) -> str:
    total_seconds = max(0, int(duration.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}小时{minutes:02d}分{seconds:02d}秒"
    if minutes:
        return f"{minutes}分{seconds:02d}秒"
    return f"{seconds}秒"


def format_task_row(task: CompletedTask) -> tuple[str, str, str]:
    started = task.started_at.strftime("%H:%M")
    duration = format_duration(task.duration)
    name = " ".join(task.name.split())
    return started, duration, name
