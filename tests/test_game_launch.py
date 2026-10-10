"""Regression tests for the original game's launch contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from better_clx.services.launcher import LaunchResult, game_executable_path, launch_game, run_as_admin
from better_clx.services.settings import AppSettings


class GameLaunchTests(unittest.TestCase):
    def _game_tree(self, root: Path) -> None:
        (root / "Engine" / "Binaries" / "Win64").mkdir(parents=True)
        (root / "Engine" / "Binaries" / "Win32").mkdir(parents=True)
        (root / "Engine" / "Binaries" / "Win64" / "wyclx64.exe").touch()
        (root / "Engine" / "Binaries" / "Win32" / "wyclx.exe").touch()
        (root / "Launcher.exe").touch()

    def test_launch_uses_full_executable_string_and_game_root_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._game_tree(root)
            settings = AppSettings(game_path=str(root), game_version="auto")

            with patch("better_clx.services.launcher.run_as_admin") as run_as_admin_mock:
                run_as_admin_mock.return_value = LaunchResult(True, "ok")
                result = launch_game(settings)

            self.assertTrue(result.success)
            self.assertEqual(run_as_admin_mock.call_args.args[0], root / "Launcher.exe")
            self.assertEqual(run_as_admin_mock.call_args.args[1], root)

    def test_version_choices_resolve_original_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._game_tree(root)
            self.assertEqual(game_executable_path(AppSettings(str(root), "64")).name, "wyclx64.exe")
            self.assertEqual(game_executable_path(AppSettings(str(root), "32")).name, "wyclx.exe")
            self.assertEqual(game_executable_path(AppSettings(str(root), "auto")).name, "Launcher.exe")

    def test_existing_process_does_not_block_multi_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._game_tree(root)
            settings = AppSettings(game_path=str(root), game_version="auto")
            with patch("better_clx.services.launcher.run_as_admin") as run_as_admin_mock:
                run_as_admin_mock.return_value = LaunchResult(True, "ok")
                first = launch_game(settings)
                second = launch_game(settings)
            self.assertTrue(first.success)
            self.assertTrue(second.success)
            self.assertEqual(run_as_admin_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
