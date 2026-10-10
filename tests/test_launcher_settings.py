"""Tests for launcher services and persistent multi-script settings."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from better_clx.services.launcher import game_executable_path, launch_game, launch_script, search_wyclx_folder
from better_clx.services.settings import AppSettings, ScriptConfig, SettingsStore


class LauncherSettingsTests(unittest.TestCase):
    def test_window_geometry_round_trip_through_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "user_setting.json"
            store = SettingsStore(settings_path, Path(temp_dir) / "missing.ini")
            settings = AppSettings(window_x=120, window_y=240, window_width=1280, window_height=800)
            store.save(settings)
            loaded = store.load()
            self.assertEqual((loaded.window_x, loaded.window_y, loaded.window_width, loaded.window_height), (120, 240, 1280, 800))

    def test_invalid_window_geometry_uses_safe_minimums(self) -> None:
        settings = AppSettings.from_dict({"window_x": "bad", "window_y": "8", "window_width": 10, "window_height": "bad"})
        self.assertIsNone(settings.window_x)
        self.assertEqual(settings.window_y, 8)
        self.assertEqual(settings.window_width, 640)
        self.assertEqual(settings.window_height, 720)

    def test_multiple_scripts_round_trip_through_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "user_setting.json"
            store = SettingsStore(settings_path, Path(temp_dir) / "missing.ini")
            settings = AppSettings(
                game_path="D:/wyclx",
                game_version="64",
                scripts=[
                    ScriptConfig(name="日常", path="D:/scripts/daily.bat", update_url="https://example.test/daily"),
                    ScriptConfig(name="采集", path="D:/scripts/gather.py", update_url="https://example.test/gather"),
                ],
            )

            store.save(settings)
            loaded = store.load()

            self.assertEqual(loaded.game_path, "D:/wyclx")
            self.assertEqual(loaded.game_version, "64")
            self.assertEqual([script.name for script in loaded.scripts], ["日常", "采集"])
            self.assertEqual(loaded.scripts[1].update_url, "https://example.test/gather")
            self.assertTrue(settings_path.is_file())

    def test_legacy_ini_migrates_single_script_and_game_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_path = Path(temp_dir) / "user_setting.ini"
            legacy_path.write_text(
                """[Path]\n"
                "game_path = D:/wyclx\n"
                "64x_relative_path = Engine\\Binaries\\Win64\\wyclx64.exe\n"
                "32x_relative_path = Engine\\Binaries\\Win32\\wyclx.exe\n"
                "launch_path = Launcher.exe\n"
                "tool_path = D:/scripts/legacy.bat\n"
                "\n"
                "[last_save]\n"
                "version_choice = 32\n"
                "\n"
                "[web]\n"
                "url = https://example.test/update\n"
                "\n"
                "[setting]\n"
                "search_timeout = 7\n""".replace('"\n                "', "\n"),
                encoding="utf-8",
            )
            settings_path = Path(temp_dir) / "user_setting.json"
            loaded = SettingsStore(settings_path, legacy_path).load()

            self.assertEqual(loaded.game_path, "D:/wyclx")
            self.assertEqual(loaded.game_version, "32")
            self.assertEqual(loaded.search_timeout, 7)
            self.assertEqual(len(loaded.scripts), 1)
            self.assertEqual(loaded.scripts[0].path, "D:/scripts/legacy.bat")
            self.assertEqual(loaded.scripts[0].update_url, "https://example.test/update")
            self.assertTrue(settings_path.is_file())

    def test_game_version_resolution_prefers_expected_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            game_dir = Path(temp_dir)
            (game_dir / "Engine" / "Binaries" / "Win64").mkdir(parents=True)
            (game_dir / "Engine" / "Binaries" / "Win32").mkdir(parents=True)
            (game_dir / "Engine" / "Binaries" / "Win64" / "wyclx64.exe").touch()
            (game_dir / "Engine" / "Binaries" / "Win32" / "wyclx.exe").touch()
            (game_dir / "Launcher.exe").touch()

            self.assertTrue(game_executable_path(AppSettings(str(game_dir), "64")).name == "wyclx64.exe")
            self.assertTrue(game_executable_path(AppSettings(str(game_dir), "32")).name == "wyclx.exe")
            self.assertTrue(game_executable_path(AppSettings(str(game_dir), "auto")).name == "Launcher.exe")

    def test_bfs_finds_valid_wyclx_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "level-one" / "wyclx"
            (game_dir / "Engine" / "Binaries" / "Win64").mkdir(parents=True)
            (game_dir / "Engine" / "Binaries" / "Win32").mkdir(parents=True)
            (game_dir / "Engine" / "Binaries" / "Win64" / "wyclx64.exe").touch()
            (game_dir / "Engine" / "Binaries" / "Win32" / "wyclx.exe").touch()

            result = search_wyclx_folder(timeout=2, roots=[root])

            self.assertEqual(Path(result), game_dir)

    def test_python_script_uses_current_python_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "demo.py"
            script_path.write_text("print('ok')\n", encoding="utf-8")
            script = ScriptConfig(name="演示", path=str(script_path))

            with patch("better_clx.services.launcher.subprocess.Popen") as popen:
                result = launch_script(script)

            self.assertTrue(result.success)
            command = popen.call_args.args[0]
            self.assertEqual(command[0], __import__("sys").executable)
            self.assertEqual(command[1], str(script_path))
            self.assertEqual(popen.call_args.kwargs["cwd"], str(script_path.parent))


if __name__ == "__main__":
    unittest.main()
