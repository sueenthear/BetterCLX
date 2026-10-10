"""Win32 window enumeration for game and login ownership detection."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from better_clx.config import (
    GAME_PROCESS_NAMES,
    GAME_TITLE_KEYWORDS,
    LOGIN_TITLE_KEYWORDS,
    LOGIN_WINDOW_CLASSES,
)
from better_clx.models import GameWindow

_USER32 = ctypes.WinDLL("user32", use_last_error=True) if os.name == "nt" else None
_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None

if _USER32 is not None:
    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _USER32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
    _USER32.EnumWindows.restype = wintypes.BOOL
    _USER32.IsWindowVisible.argtypes = [wintypes.HWND]
    _USER32.IsWindowVisible.restype = wintypes.BOOL
    _USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _USER32.GetWindowTextLengthW.restype = ctypes.c_int
    _USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _USER32.GetWindowTextW.restype = ctypes.c_int
    _USER32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _USER32.GetClassNameW.restype = ctypes.c_int
    _USER32.GetParent.argtypes = [wintypes.HWND]
    _USER32.GetParent.restype = wintypes.HWND
    _USER32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _USER32.GetClientRect.restype = wintypes.BOOL
    _USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _USER32.GetWindowThreadProcessId.restype = wintypes.DWORD

    _KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _KERNEL32.OpenProcess.restype = wintypes.HANDLE
    _KERNEL32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _KERNEL32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = wintypes.BOOL

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _text(hwnd: int, class_name: bool = False) -> str:
    if _USER32 is None:
        return ""
    if class_name:
        buffer = ctypes.create_unicode_buffer(256)
        _USER32.GetClassNameW(hwnd, buffer, len(buffer))
        return buffer.value
    length = _USER32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(max(length + 1, 1))
    _USER32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def _pid_for_window(hwnd: int) -> int:
    if _USER32 is None:
        return 0
    pid = wintypes.DWORD()
    _USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _process_name(pid: int) -> str:
    if _KERNEL32 is None or not pid:
        return ""
    handle = _KERNEL32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not _KERNEL32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return os.path.basename(buffer.value)
    finally:
        _KERNEL32.CloseHandle(handle)


def _client_size(hwnd: int) -> tuple[int, int]:
    if _USER32 is None:
        return 0, 0
    rect = wintypes.RECT()
    if not _USER32.GetClientRect(hwnd, ctypes.byref(rect)):
        return 0, 0
    return max(0, rect.right - rect.left), max(0, rect.bottom - rect.top)


def _all_windows() -> list[dict[str, int | str]]:
    """Return visible top-level windows with their basic Win32 metadata."""
    if _USER32 is None:
        return []
    windows: list[dict[str, int | str]] = []

    @_WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        if not _USER32.IsWindowVisible(hwnd):
            return True
        pid = _pid_for_window(hwnd)
        if not pid:
            return True
        windows.append(
            {
                "hwnd": int(hwnd),
                "pid": pid,
                "title": _text(hwnd),
                "class_name": _text(hwnd, class_name=True),
                "parent": int(_USER32.GetParent(hwnd) or 0),
            }
        )
        return True

    _USER32.EnumWindows(callback, 0)
    return windows


def _is_game_window(window: dict[str, int | str]) -> bool:
    title = str(window["title"])
    if int(window["parent"]):
        return False
    if not title or not any(keyword in title for keyword in GAME_TITLE_KEYWORDS):
        return False
    process_name = _process_name(int(window["pid"]))
    return process_name.lower() in {name.lower() for name in GAME_PROCESS_NAMES}


def detect_game_windows() -> list[GameWindow]:
    """Find game windows and attach a login window owned by the same PID."""
    windows = _all_windows()
    login_by_pid: dict[int, int] = {}
    for window in windows:
        class_name = str(window["class_name"])
        title = str(window["title"])
        if class_name in LOGIN_WINDOW_CLASSES or any(keyword in title for keyword in LOGIN_TITLE_KEYWORDS):
            login_by_pid[int(window["pid"])] = int(window["hwnd"])

    detected: list[GameWindow] = []
    for window in windows:
        if not _is_game_window(window):
            continue
        hwnd = int(window["hwnd"])
        pid = int(window["pid"])
        width, height = _client_size(hwnd)
        detected.append(
            GameWindow(
                hwnd=hwnd,
                pid=pid,
                title=str(window["title"]),
                process_name=_process_name(pid),
                client_width=width,
                client_height=height,
                login_hwnd=login_by_pid.get(pid),
            )
        )
    return sorted(detected, key=lambda item: item.hwnd)
