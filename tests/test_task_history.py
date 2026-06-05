from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from src.desktop_timer.task_history import (
    CompletedTask,
    RunningTask,
    format_duration,
    format_task_row,
    merge_into_completed,
)


class TaskHistoryTest(unittest.TestCase):
    def test_format_duration(self) -> None:
        self.assertEqual(format_duration(timedelta(seconds=0)), "0秒")
        self.assertEqual(format_duration(timedelta(seconds=9)), "9秒")
        self.assertEqual(format_duration(timedelta(minutes=2, seconds=5)), "2分05秒")
        self.assertEqual(format_duration(timedelta(hours=1, minutes=2, seconds=5)), "1小时02分05秒")

    def test_format_task_row(self) -> None:
        task = CompletedTask(
            started_at=datetime(2026, 6, 2, 9, 30),
            finished_at=datetime(2026, 6, 2, 9, 55),
            duration=timedelta(minutes=25, seconds=13),
            name="  写   周报  ",
        )

        self.assertEqual(format_task_row(task), ("09:30", "25分13秒", "写 周报"))


class RunningTaskTest(unittest.TestCase):
    def _make(self, t0: float = 100.0) -> RunningTask:
        return RunningTask(
            name="写稿子",
            started_at=datetime(2026, 6, 4, 9, 0),
            state="running",
            elapsed_before_run=0.0,
            run_started_monotonic=t0,
        )

    def test_running_task_elapsed_includes_current_segment(self) -> None:
        task = self._make(t0=100.0)
        self.assertAlmostEqual(task.elapsed_seconds(now_monotonic=130.0), 30.0)

    def test_running_task_pause_accumulates_elapsed(self) -> None:
        task = self._make(t0=100.0)
        task.pause(now_monotonic=125.0)
        self.assertEqual(task.state, "paused")
        self.assertAlmostEqual(task.elapsed_before_run, 25.0)
        self.assertIsNone(task.run_started_monotonic)
        self.assertAlmostEqual(task.elapsed_seconds(now_monotonic=200.0), 25.0)

    def test_running_task_resume_continues(self) -> None:
        task = self._make(t0=100.0)
        task.pause(now_monotonic=125.0)
        task.resume(now_monotonic=300.0)
        self.assertEqual(task.state, "running")
        self.assertAlmostEqual(task.elapsed_seconds(now_monotonic=310.0), 35.0)


class MergeIntoCompletedTest(unittest.TestCase):
    def _make_completed(
        self,
        name: str,
        start: datetime,
        end: datetime,
        duration_seconds: int,
        merge_count: int = 1,
    ) -> CompletedTask:
        return CompletedTask(
            started_at=start,
            finished_at=end,
            duration=timedelta(seconds=duration_seconds),
            name=name,
            merge_count=merge_count,
        )

    def test_merge_into_empty_completed(self) -> None:
        completed: list[CompletedTask] = []
        finished = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 9, 0),
            datetime(2026, 6, 4, 9, 30),
            1800,
        )
        merge_into_completed(completed, finished)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].name, "写稿子")
        self.assertEqual(completed[0].merge_count, 1)

    def test_merge_into_different_name_inserts_at_top(self) -> None:
        existing = self._make_completed(
            "客户对接",
            datetime(2026, 6, 4, 9, 0),
            datetime(2026, 6, 4, 9, 10),
            600,
        )
        completed = [existing]
        finished = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 10, 0),
            datetime(2026, 6, 4, 10, 30),
            1800,
        )
        merge_into_completed(completed, finished)
        self.assertEqual(len(completed), 2)
        self.assertEqual(completed[0].name, "写稿子")
        self.assertEqual(completed[1].name, "客户对接")

    def test_merge_into_existing_same_name_moves_to_top(self) -> None:
        other = self._make_completed(
            "客户对接",
            datetime(2026, 6, 4, 9, 0),
            datetime(2026, 6, 4, 9, 10),
            600,
        )
        existing = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 8, 0),
            datetime(2026, 6, 4, 8, 30),
            1800,
        )
        completed = [other, existing]
        finished = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 11, 0),
            datetime(2026, 6, 4, 11, 5),
            300,
        )
        merge_into_completed(completed, finished)
        self.assertEqual(len(completed), 2)
        self.assertEqual(completed[0].name, "写稿子")
        self.assertEqual(completed[1].name, "客户对接")

    def test_merge_uses_earliest_started_at(self) -> None:
        existing = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 8, 0),
            datetime(2026, 6, 4, 8, 30),
            1800,
        )
        completed = [existing]
        finished = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 11, 0),
            datetime(2026, 6, 4, 11, 5),
            300,
        )
        merge_into_completed(completed, finished)
        self.assertEqual(completed[0].started_at, datetime(2026, 6, 4, 8, 0))

    def test_merge_uses_latest_finished_at(self) -> None:
        existing = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 8, 0),
            datetime(2026, 6, 4, 8, 30),
            1800,
        )
        completed = [existing]
        finished = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 11, 0),
            datetime(2026, 6, 4, 11, 5),
            300,
        )
        merge_into_completed(completed, finished)
        self.assertEqual(completed[0].finished_at, datetime(2026, 6, 4, 11, 5))

    def test_merge_sums_duration(self) -> None:
        existing = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 8, 0),
            datetime(2026, 6, 4, 8, 30),
            1800,
        )
        completed = [existing]
        finished = self._make_completed(
            "写稿子",
            datetime(2026, 6, 4, 11, 0),
            datetime(2026, 6, 4, 11, 5),
            300,
        )
        merge_into_completed(completed, finished)
        self.assertEqual(completed[0].duration, timedelta(seconds=2100))

    def test_merge_count_increments(self) -> None:
        completed: list[CompletedTask] = []
        for hour in (8, 9, 10):
            finished = self._make_completed(
                "写稿子",
                datetime(2026, 6, 4, hour, 0),
                datetime(2026, 6, 4, hour, 5),
                300,
            )
            merge_into_completed(completed, finished)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].merge_count, 3)
        self.assertEqual(completed[0].duration, timedelta(seconds=900))

    def test_merge_strips_name_for_comparison(self) -> None:
        existing = self._make_completed(
            "写稿",
            datetime(2026, 6, 4, 8, 0),
            datetime(2026, 6, 4, 8, 30),
            1800,
        )
        completed = [existing]
        finished = self._make_completed(
            "  写稿  ",
            datetime(2026, 6, 4, 9, 0),
            datetime(2026, 6, 4, 9, 5),
            300,
        )
        merge_into_completed(completed, finished)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].merge_count, 2)


if __name__ == "__main__":
    unittest.main()
