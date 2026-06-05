from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.desktop_timer.obsidian_writer import (
    DailyNoteMissingError,
    TaskRecord,
    append_record,
    daily_note_path,
    format_duration,
    format_record,
)


class ObsidianWriterTest(unittest.TestCase):
    def test_daily_note_path_uses_yyyy_mm_dd(self) -> None:
        path = daily_note_path(Path("notes"), datetime(2026, 6, 2).date())

        self.assertEqual(path, Path("notes") / "2026-06-02.md")

    def test_format_duration_omits_empty_units(self) -> None:
        self.assertEqual(format_duration(timedelta(seconds=0)), "0秒")
        self.assertEqual(format_duration(timedelta(seconds=13)), "13秒")
        self.assertEqual(format_duration(timedelta(minutes=25, seconds=13)), "25分13秒")
        self.assertEqual(format_duration(timedelta(hours=1, minutes=2)), "1小时2分")

    def test_format_record_collapses_task_whitespace(self) -> None:
        record = TaskRecord(
            started_at=datetime(2026, 6, 2, 9, 30),
            duration=timedelta(minutes=25, seconds=13),
            task="  写   周报  ",
        )

        self.assertEqual(format_record(record), "- 09:30｜用时 25分13秒｜写 周报")

    def test_append_record_appends_to_existing_daily_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            note_dir = Path(temp_dir)
            note_path = note_dir / "2026-06-02.md"
            note_path.write_text("# Daily Note\n", encoding="utf-8")
            record = TaskRecord(
                started_at=datetime(2026, 6, 2, 9, 30),
                duration=timedelta(minutes=25, seconds=13),
                task="写周报",
            )

            result = append_record(note_dir, record)

            self.assertEqual(result, note_path)
            self.assertEqual(
                note_path.read_text(encoding="utf-8"),
                "# Daily Note\n- 09:30｜用时 25分13秒｜写周报\n",
            )

    def test_append_record_does_not_create_missing_daily_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            note_dir = Path(temp_dir)
            record = TaskRecord(
                started_at=datetime(2026, 6, 2, 9, 30),
                duration=timedelta(minutes=1),
                task="写周报",
            )

            with self.assertRaises(DailyNoteMissingError):
                append_record(note_dir, record)

            self.assertFalse((note_dir / "2026-06-02.md").exists())


if __name__ == "__main__":
    unittest.main()
