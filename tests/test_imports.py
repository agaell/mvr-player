"""Import smoke tests for the project skeleton."""

import json
import tempfile
import unittest
from pathlib import Path


class ImportTests(unittest.TestCase):
    def test_core_modules_import(self) -> None:
        import mvr_player
        from mvr_player import app
        from mvr_player import converter
        from mvr_player import errors
        from mvr_player import ffmpeg_utils
        from mvr_player import main
        from mvr_player import player
        from mvr_player import settings
        from mvr_player import ui
        from mvr_player import utils

        self.assertTrue(mvr_player.__version__)
        self.assertEqual(mvr_player.__version__, "0.1.0")
        self.assertEqual(settings.APP_NAME, "MVR Player")
        self.assertEqual(settings.APP_VERSION, "0.1.0")
        self.assertTrue(app)
        self.assertTrue(converter)
        self.assertTrue(errors)
        self.assertTrue(ffmpeg_utils)
        self.assertTrue(main)
        self.assertTrue(player)
        self.assertTrue(ui)
        self.assertTrue(utils)

    def test_ffmpeg_error_message_is_user_friendly(self) -> None:
        from mvr_player.errors import user_message

        message = user_message("Invalid data found when processing input")

        self.assertIn("FFmpeg", message)
        self.assertIn("файл", message)

    def test_user_settings_remember_folders_outside_repository(self) -> None:
        from mvr_player.settings import UserSettings

        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_file = Path(temporary_directory) / "settings.json"
            open_directory = Path(temporary_directory) / "open"
            output_directory = Path(temporary_directory) / "output"
            open_directory.mkdir()
            output_directory.mkdir()

            preferences = UserSettings.load(settings_file)
            preferences.remember_open_directory(open_directory)
            preferences.remember_mp4_output_directory(output_directory)

            restored_preferences = UserSettings.load(settings_file)

            self.assertEqual(restored_preferences.last_open_directory, open_directory)
            self.assertEqual(restored_preferences.mp4_output_directory, output_directory)
            self.assertEqual(
                json.loads(settings_file.read_text(encoding="utf-8")),
                {
                    "last_open_directory": str(open_directory),
                    "mp4_output_directory": str(output_directory),
                },
            )

    def test_folder_scan_finds_mvr_files_in_subdirectories(self) -> None:
        from mvr_player.ui import _find_mvr_files

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested_directory = root / "recordings" / "night"
            nested_directory.mkdir(parents=True)
            (root / "camera-a.mvr").touch()
            (nested_directory / "camera-b.MVR").touch()
            (nested_directory / "notes.txt").touch()

            files, skipped_directories = _find_mvr_files(root)

            self.assertEqual(files, [root / "camera-a.mvr", nested_directory / "camera-b.MVR"])
            self.assertEqual(skipped_directories, 0)

    def test_file_count_uses_russian_plural_forms(self) -> None:
        from mvr_player.ui import _format_file_count

        self.assertEqual(_format_file_count(1), "1 файл")
        self.assertEqual(_format_file_count(2), "2 файла")
        self.assertEqual(_format_file_count(5), "5 файлов")
        self.assertEqual(_format_file_count(11), "11 файлов")
        self.assertEqual(_format_file_count(21), "21 файл")


if __name__ == "__main__":
    unittest.main()
