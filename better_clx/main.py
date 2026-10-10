"""Better CLX application entrypoint with UAC and single-instance control."""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from better_clx.config import APP_NAME
from better_clx.runtime_paths import SOURCE_ROOT, install_root, resource_path
from better_clx.ui.main_window import MainWindow
from better_clx.ui.splash import StartupSplash

_UAC_FLAG = "--uac-elevated"
_MUTEX_NAME = "Local\\Better-CLX-SingleInstance"
_WAIT_FOR_PARENT_MS = 5000


class SingleInstanceLock:
    """Process-wide named lock with an explicit UAC handoff."""

    def __init__(self, name: str = _MUTEX_NAME, lock_path: Path | None = None) -> None:
        self.name = name
        self.lock_path = lock_path
        self.handle: int | None = None
        self._lock_file = None

    def acquire(self, wait_ms: int = 0) -> bool:
        if os.name == "nt":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            kernel32.GetLastError.restype = wintypes.DWORD
            handle = kernel32.CreateMutexW(None, True, self.name)
            if not handle:
                return False
            already_exists = kernel32.GetLastError() == 183
            if already_exists:
                result = kernel32.WaitForSingleObject(handle, max(0, wait_ms))
                if result != 0:
                    kernel32.CloseHandle(handle)
                    return False
            self.handle = int(handle)
            self._kernel32 = kernel32
            return True

        lock_path = self.lock_path or (Path(os.environ.get("TEMP", "/tmp")) / "better-clx-single-instance.lock")
        try:
            self._lock_file = lock_path.open("x", encoding="ascii")
            return True
        except FileExistsError:
            return False

    def release(self) -> None:
        if self.handle is not None:
            self._kernel32.ReleaseMutex(self.handle)
            self._kernel32.CloseHandle(self.handle)
            self.handle = None
        if self._lock_file is not None:
            path = Path(self._lock_file.name)
            self._lock_file.close()
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            self._lock_file = None


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relaunch_as_admin() -> bool:
    if os.name != "nt":
        return False
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteW.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_int,
    ]
    shell32.ShellExecuteW.restype = wintypes.HINSTANCE
    if getattr(sys, "frozen", False):
        executable = str(Path(sys.executable).resolve())
        parameters = _UAC_FLAG
        working_directory = str(install_root())
    else:
        executable = sys.executable
        parameters = "-m better_clx.main " + _UAC_FLAG
        working_directory = str(SOURCE_ROOT)
    result = shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        working_directory,
        1,
    )
    return result > 32


def ensure_admin() -> bool:
    if _UAC_FLAG in sys.argv:
        return is_admin()
    if is_admin():
        return True
    return relaunch_as_admin()


def main() -> int:
    lock = SingleInstanceLock()
    elevated_child = _UAC_FLAG in sys.argv
    if elevated_child:
        # The non-elevated parent releases its mutex immediately after ShellExecuteW returns.
        deadline = time.monotonic() + _WAIT_FOR_PARENT_MS / 1000
        while not lock.acquire(100) and time.monotonic() < deadline:
            time.sleep(0.05)
        if lock.handle is None and not lock.acquire(0):
            return 2
    elif not lock.acquire(0):
        return 0

    try:
        if elevated_child:
            if not ensure_admin():
                return 1
        elif not is_admin():
            # The parent only owns the lock during UAC handoff, then exits.
            if not ensure_admin():
                return 1
            return 0

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setOrganizationName("Better CLX")
        icon = QIcon(str(resource_path("icon.ico")))
        app.setWindowIcon(icon)
        setTheme(Theme.AUTO)

        splash = StartupSplash()
        splash.setWindowIcon(icon)
        splash.show()
        startup_started = time.monotonic()
        splash.update_progress(8, "正在初始化界面…")
        for value in range(12, 31, 3):
            time.sleep(0.035)
            splash.update_progress(value, "正在初始化界面…")
        window = MainWindow()
        for value in range(34, 76, 3):
            time.sleep(0.035)
            splash.update_progress(value, "正在加载窗口监控…")
        window.setWindowIcon(icon)
        for value in range(78, 101, 2):
            time.sleep(0.035)
            splash.update_progress(value, "正在完成启动…" if value < 100 else "启动完成")
        elapsed = time.monotonic() - startup_started
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        splash.close()
        window.show()
        QTimer.singleShot(0, window.apply_saved_geometry)
        return app.exec()
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
