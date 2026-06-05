from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.desktop_timer.settings import Settings, load_settings, save_settings


class SettingsTest(unittest.TestCase):
    def test_missing_settings_returns_empty_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"

            settings = load_settings(settings_path)

            self.assertIsNone(settings.daily_note_dir)

    def test_save_and_load_daily_note_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            daily_note_dir = Path(temp_dir) / "notes"

            save_settings(Settings(daily_note_dir=daily_note_dir), settings_path)
            loaded = load_settings(settings_path)

            self.assertEqual(loaded.daily_note_dir, daily_note_dir)

    def test_invalid_json_returns_empty_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            settings_path.write_text("{invalid", encoding="utf-8")

            settings = load_settings(settings_path)

            self.assertIsNone(settings.daily_note_dir)


if __name__ == "__main__":
    unittest.main()
