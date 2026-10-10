"""Tests for PID-based game/login window association."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from better_clx.models import WindowStatus
from better_clx.platform.windows import detect_game_windows


class DetectGameWindowsTests(unittest.TestCase):
    def test_login_window_only_marks_game_with_same_pid(self) -> None:
        fake_windows = [
            {"hwnd": 0x1000, "pid": 101, "title": "一梦江湖", "class_name": "Messiah_Game", "parent": 0},
            {"hwnd": 0x1001, "pid": 101, "title": "登录", "class_name": "MPAY_LOGIN", "parent": 0},
            {"hwnd": 0x2000, "pid": 202, "title": "一梦江湖", "class_name": "Messiah_Game", "parent": 0},
        ]

        def process_name(pid: int) -> str:
            return "wyclx64.exe" if pid == 101 else "wyclx.exe"

        with (
            patch("better_clx.platform.windows._all_windows", return_value=fake_windows),
            patch("better_clx.platform.windows._process_name", side_effect=process_name),
            patch("better_clx.platform.windows._client_size", return_value=(1280, 720)),
        ):
            games = detect_game_windows()

        self.assertEqual([game.pid for game in games], [101, 202])
        self.assertEqual(games[0].login_hwnd, 0x1001)
        self.assertIs(games[0].status, WindowStatus.LOGGING_IN)
        self.assertIsNone(games[1].login_hwnd)
        self.assertIs(games[1].status, WindowStatus.RUNNING)

    def test_login_window_of_non_game_process_is_ignored(self) -> None:
        fake_windows = [
            {"hwnd": 0x3000, "pid": 303, "title": "一梦江湖", "class_name": "Messiah_Game", "parent": 0},
            {"hwnd": 0x3001, "pid": 404, "title": "登录", "class_name": "MPAY_LOGIN", "parent": 0},
        ]

        with (
            patch("better_clx.platform.windows._all_windows", return_value=fake_windows),
            patch("better_clx.platform.windows._process_name", return_value="wyclx64.exe"),
            patch("better_clx.platform.windows._client_size", return_value=(800, 600)),
        ):
            games = detect_game_windows()

        self.assertEqual(len(games), 1)
        self.assertIsNone(games[0].login_hwnd)
        self.assertIs(games[0].status, WindowStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
