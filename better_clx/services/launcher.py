"""Game/script launch operations and game directory discovery."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import webbrowser
from ctypes import wintypes
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from better_clx.services.settings import AppSettings, ScriptConfig


@dataclass(frozen=True, slots=True)
class LaunchResult:
    success: bool
    message: str


def game_executable_path(settings: AppSettings) -> Path | None:
    """Resolve the selected game entry point from the configured game directory."""
    if not settings.game_path:
        return None
    game_dir = Path(settings.game_path).expanduser()
    candidates: list[Path]
    if settings.game_version == "64":
        candidates = [game_dir / settings.game_64_relative_path]
    elif settings.game_version == "32":
        candidates = [game_dir / settings.game_32_relative_path]
    else:
        # Match the original project: auto mode starts Launcher.exe first so it
        # can apply the game's update/version selection before launching.
        candidates = [
            game_dir / settings.game_launch_relative_path,
            game_dir / settings.game_64_relative_path,
            game_dir / settings.game_32_relative_path,
        ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def game_status(settings: AppSettings) -> tuple[bool, str]:
    """Return whether the current selection can be launched and a user-facing detail."""
    if not settings.game_path:
        return False, "尚未设置游戏路径"
    game_dir = Path(settings.game_path).expanduser()
    if not game_dir.is_dir():
        return False, f"游戏目录不存在: {game_dir}"
    executable = game_executable_path(settings)
    if executable is None:
        return False, "找不到当前版本对应的启动文件"
    return True, f"已找到 {executable.name}"


def run_as_admin(executable: Path, working_directory: Path) -> LaunchResult:
    """Start a game executable through the Windows UAC consent flow."""
    if os.name != "nt":
        return LaunchResult(False, "UAC 提权仅支持 Windows")
    try:
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
        result = shell32.ShellExecuteW(
            None,
            "runas",
            str(executable),
            None,
            str(working_directory),
            1,
        )
    except OSError as exc:
        return LaunchResult(False, f"UAC 提权启动失败: {exc}")
    if result <= 32:
        if result == 5:
            return LaunchResult(False, "已取消管理员权限，游戏未启动")
        return LaunchResult(False, f"UAC 提权启动失败，ShellExecute 错误码: {result}")
    return LaunchResult(True, f"已请求管理员权限启动: {executable.name}")


def launch_game(settings: AppSettings) -> LaunchResult:
    executable = game_executable_path(settings)
    if executable is None:
        valid, detail = game_status(settings)
        return LaunchResult(False, detail if not valid else "找不到游戏启动文件")
    game_dir = Path(settings.game_path).expanduser()
    return run_as_admin(executable, game_dir)


def launch_script(script: ScriptConfig) -> LaunchResult:
    """Launch one script with its own working directory."""
    if not script.path:
        return LaunchResult(False, f"{script.name} 尚未选择脚本")
    script_path = Path(script.path).expanduser()
    if not script_path.is_file():
        return LaunchResult(False, f"脚本文件不存在: {script_path}")

    work_dir = str(script_path.parent)
    suffix = script_path.suffix.lower()
    if suffix in {".bat", ".cmd"}:
        command = ["cmd.exe", "/d", "/c", str(script_path)]
    elif suffix == ".py":
        command = [sys.executable, str(script_path)]
    else:
        command = [str(script_path)]
    try:
        subprocess.Popen(command, cwd=work_dir)
    except OSError as exc:
        return LaunchResult(False, f"脚本启动失败: {exc}")
    return LaunchResult(True, f"已启动脚本: {script.name}")


def open_update_url(script: ScriptConfig) -> LaunchResult:
    if not script.update_url.strip():
        return LaunchResult(False, f"{script.name} 尚未配置更新网址")
    try:
        webbrowser.open(script.update_url.strip())
    except OSError as exc:
        return LaunchResult(False, f"打开更新网址失败: {exc}")
    return LaunchResult(True, "已打开更新网址")


def _has_game_files(directory: Path, required_files: Iterable[str]) -> bool:
    return all((directory / relative_path).is_file() for relative_path in required_files)


def search_wyclx_folder(timeout: int = 10, roots: Iterable[Path] | None = None) -> str:
    """Breadth-first search for a valid wyclx install directory.

    ``roots`` is injectable for tests; normal use starts at every mounted Windows drive.
    """
    required_files = (
        Path(r"Engine\Binaries\Win64\wyclx64.exe"),
        Path(r"Engine\Binaries\Win32\wyclx.exe"),
    )
    if roots is None:
        roots = (Path(f"{letter}:\\") for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:\\").exists())

    deadline = time.monotonic() + max(1, timeout)
    queue: deque[Path] = deque(Path(root) for root in roots)
    skipped_root_dirs = {
        "Windows",
        "Program Files",
        "Program Files (x86)",
        "ProgramData",
        "$Recycle.Bin",
        "System Volume Information",
    }

    while queue and time.monotonic() < deadline:
        current = queue.popleft()
        try:
            if current.name.lower() == "wyclx" and _has_game_files(current, required_files):
                return str(current)
            entries = list(os.scandir(current))
        except (OSError, PermissionError):
            continue

        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if current.parent == current and entry.name in skipped_root_dirs:
                continue
            queue.append(Path(entry.path))
    return ""
