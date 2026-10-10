"""Tests for Windows UAC game launch result handling."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from better_clx.services.launcher import run_as_admin


class UacLaunchTests(unittest.TestCase):
    def _shell32(self, result: int) -> MagicMock:
        shell32 = MagicMock()
        shell32.ShellExecuteW.return_value = result
        return shell32

    def test_uac_success_returns_success(self) -> None:
        shell32 = self._shell32(33)
        with patch("better_clx.services.launcher.os.name", "nt"), patch(
            "better_clx.services.launcher.ctypes.WinDLL", return_value=shell32
        ):
            result = run_as_admin(Path("C:/game/Launcher.exe"), Path("C:/game"))
        self.assertTrue(result.success)
        self.assertIn("管理员权限", result.message)
        self.assertEqual(shell32.ShellExecuteW.call_args.args[1], "runas")
        self.assertEqual(Path(shell32.ShellExecuteW.call_args.args[2]), Path("C:/game/Launcher.exe"))
        self.assertEqual(Path(shell32.ShellExecuteW.call_args.args[4]), Path("C:/game"))

    def test_uac_cancel_returns_actionable_error(self) -> None:
        shell32 = self._shell32(5)
        with patch("better_clx.services.launcher.os.name", "nt"), patch(
            "better_clx.services.launcher.ctypes.WinDLL", return_value=shell32
        ):
            result = run_as_admin(Path("C:/game/Launcher.exe"), Path("C:/game"))
        self.assertFalse(result.success)
        self.assertIn("取消管理员权限", result.message)

    def test_uac_failure_returns_shell_execute_code(self) -> None:
        shell32 = self._shell32(31)
        with patch("better_clx.services.launcher.os.name", "nt"), patch(
            "better_clx.services.launcher.ctypes.WinDLL", return_value=shell32
        ):
            result = run_as_admin(Path("C:/game/Launcher.exe"), Path("C:/game"))
        self.assertFalse(result.success)
        self.assertIn("31", result.message)


if __name__ == "__main__":
    unittest.main()
