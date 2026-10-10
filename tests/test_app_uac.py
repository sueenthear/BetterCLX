"""Tests for process-level UAC bootstrap decisions."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from better_clx import main as app_main


class AppUacTests(unittest.TestCase):
    def test_elevated_flag_does_not_relaunch(self) -> None:
        with (
            patch.object(app_main.sys, "argv", ["clx", "--uac-elevated"]),
            patch("better_clx.main.is_admin", return_value=True),
            patch("better_clx.main.relaunch_as_admin") as relaunch,
        ):
            self.assertTrue(app_main.ensure_admin())
        relaunch.assert_not_called()

    def test_admin_process_does_not_relaunch(self) -> None:
        with (
            patch.object(app_main.sys, "argv", ["clx"]),
            patch("better_clx.main.is_admin", return_value=True),
            patch("better_clx.main.relaunch_as_admin") as relaunch,
        ):
            self.assertTrue(app_main.ensure_admin())
        relaunch.assert_not_called()

    def test_non_admin_process_requests_relaunch(self) -> None:
        with (
            patch.object(app_main.sys, "argv", ["clx"]),
            patch("better_clx.main.is_admin", return_value=False),
            patch("better_clx.main.relaunch_as_admin", return_value=True) as relaunch,
        ):
            self.assertTrue(app_main.ensure_admin())
        relaunch.assert_called_once_with()

    def test_cancelled_uac_fails_bootstrap(self) -> None:
        with (
            patch.object(app_main.sys, "argv", ["clx"]),
            patch("better_clx.main.is_admin", return_value=False),
            patch("better_clx.main.relaunch_as_admin", return_value=False),
        ):
            self.assertFalse(app_main.ensure_admin())


if __name__ == "__main__":
    unittest.main()
