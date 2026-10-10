"""Tests for Better CLX single-instance and UAC handoff decisions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from better_clx.main import SingleInstanceLock


class SingleInstanceTests(unittest.TestCase):
    def test_file_lock_allows_one_owner_and_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "instance.lock"
            first = SingleInstanceLock(lock_path=lock_path)
            second = SingleInstanceLock(lock_path=lock_path)
            with patch("better_clx.main.os.name", "posix"):
                self.assertTrue(first.acquire())
                self.assertFalse(second.acquire())
                first.release()
                self.assertTrue(second.acquire())
                second.release()

    def test_non_admin_parent_exits_after_successful_handoff(self) -> None:
        import better_clx.main as app_main

        with (
            patch.object(app_main.sys, "argv", ["clx"]),
            patch.object(app_main, "is_admin", return_value=False),
            patch.object(app_main, "relaunch_as_admin", return_value=True),
            patch.object(app_main.SingleInstanceLock, "acquire", return_value=True),
            patch.object(app_main.SingleInstanceLock, "release") as release,
        ):
            result = app_main.main()
        self.assertEqual(result, 0)
        release.assert_called_once_with()

    def test_non_admin_parent_returns_error_when_uac_cancelled(self) -> None:
        import better_clx.main as app_main

        with (
            patch.object(app_main.sys, "argv", ["clx"]),
            patch.object(app_main, "is_admin", return_value=False),
            patch.object(app_main, "relaunch_as_admin", return_value=False),
            patch.object(app_main.SingleInstanceLock, "acquire", return_value=True),
            patch.object(app_main.SingleInstanceLock, "release"),
        ):
            result = app_main.main()
        self.assertEqual(result, 1)

    def test_elevated_child_does_not_launch_second_uac(self) -> None:
        import better_clx.main as app_main

        with (
            patch.object(app_main.sys, "argv", ["clx", "--uac-elevated"]),
            patch.object(app_main, "is_admin", return_value=True),
            patch.object(app_main, "relaunch_as_admin") as relaunch,
            patch.object(app_main.SingleInstanceLock, "acquire", return_value=True),
            patch.object(app_main.SingleInstanceLock, "release"),
            patch.object(app_main, "QApplication") as application,
        ):
            application.return_value.exec.return_value = 0
            result = app_main.main()
        self.assertEqual(result, 0)
        relaunch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
