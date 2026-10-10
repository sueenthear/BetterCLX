"""Window focus, single-HWND binding and fullscreen actions."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


if os.name == "nt":
    _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    _WND_STYLE = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

    _USER32.IsWindow.argtypes = [wintypes.HWND]
    _USER32.IsWindow.restype = wintypes.BOOL
    _USER32.IsWindowVisible.argtypes = [wintypes.HWND]
    _USER32.IsWindowVisible.restype = wintypes.BOOL
    _USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _USER32.ShowWindow.restype = wintypes.BOOL
    _USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _USER32.SetForegroundWindow.restype = wintypes.BOOL
    _USER32.BringWindowToTop.argtypes = [wintypes.HWND]
    _USER32.BringWindowToTop.restype = wintypes.BOOL
    _USER32.SetActiveWindow.argtypes = [wintypes.HWND]
    _USER32.SetActiveWindow.restype = wintypes.HWND
    _USER32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    _USER32.GetWindowLongPtrW.restype = _WND_STYLE
    _USER32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, _WND_STYLE]
    _USER32.SetWindowLongPtrW.restype = _WND_STYLE
    _USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _USER32.GetWindowRect.restype = wintypes.BOOL
    _USER32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    _USER32.SetWindowPos.restype = wintypes.BOOL
    _USER32.MonitorFromWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
    _USER32.MonitorFromWindow.restype = wintypes.HANDLE
    _USER32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]
    _USER32.GetMonitorInfoW.restype = wintypes.BOOL

    _SW_RESTORE = 9
    _GWL_STYLE = -16
    _WS_OVERLAPPEDWINDOW = 0x00CF0000
    _HWND_TOP = 0
    _SWP_NOZORDER = 0x0004
    _SWP_SHOWWINDOW = 0x0040
    _SWP_FRAMECHANGED = 0x0020
    _MONITOR_DEFAULTTONEAREST = 2
else:  # pragma: no cover - Windows-only calls are guarded for importability
    _USER32 = None


class WindowBindingController(QObject):
    """Own the only bound game HWND and all actions scoped to it."""

    bound_changed = Signal(object)
    fullscreen_changed = Signal(bool)
    action_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bound_hwnd: int | None = None
        self._fullscreen = False
        self._original_style: int | None = None
        self._original_rect: tuple[int, int, int, int] | None = None

    @property
    def bound_hwnd(self) -> int | None:
        return self._bound_hwnd

    @property
    def is_fullscreen(self) -> bool:
        return self._fullscreen

    @staticmethod
    def is_window(hwnd: int | None) -> bool:
        return bool(_USER32 is not None and hwnd and _USER32.IsWindow(hwnd))

    def focus_window(self, hwnd: int | None) -> bool:
        """Bring a visible target window forward after a single-click delay."""
        if not self.is_window(hwnd):
            self.action_failed.emit("目标窗口已不存在")
            return False
        if _USER32 is None:  # pragma: no cover - Windows-only behavior
            return False
        _USER32.ShowWindow(hwnd, _SW_RESTORE)
        restored = bool(_USER32.SetForegroundWindow(hwnd))
        _USER32.BringWindowToTop(hwnd)
        _USER32.SetActiveWindow(hwnd)
        if not restored:
            self.action_failed.emit("无法将目标窗口置于前台")
        return restored

    def bind_window(self, hwnd: int | None) -> bool:
        """Bind exactly one HWND; a new double-click replaces the old target."""
        if not self.is_window(hwnd):
            self.action_failed.emit("目标窗口已不存在，无法绑定")
            return False
        if self._fullscreen and self._bound_hwnd != hwnd:
            self.restore_fullscreen()
        self._bound_hwnd = int(hwnd)
        self.bound_changed.emit(self._bound_hwnd)
        return True

    def unbind(self) -> None:
        if self._fullscreen:
            self.restore_fullscreen()
        self._bound_hwnd = None
        self.bound_changed.emit(None)

    def toggle_fullscreen(self) -> bool:
        """Toggle fullscreen for the bound HWND only."""
        if self._bound_hwnd is None or not self.is_window(self._bound_hwnd):
            self.action_failed.emit("请先绑定一个有效窗口")
            return False
        if self._fullscreen:
            return self.restore_fullscreen()
        if _USER32 is None:  # pragma: no cover
            return False

        rect = wintypes.RECT()
        if not _USER32.GetWindowRect(self._bound_hwnd, ctypes.byref(rect)):
            self.action_failed.emit("无法读取绑定窗口位置")
            return False
        monitor = _USER32.MonitorFromWindow(self._bound_hwnd, _MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not monitor or not _USER32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            self.action_failed.emit("无法读取显示器信息")
            return False

        original_style = int(_USER32.GetWindowLongPtrW(self._bound_hwnd, _GWL_STYLE))
        self._original_style = original_style
        self._original_rect = (rect.left, rect.top, rect.right, rect.bottom)
        fullscreen_style = original_style & ~_WS_OVERLAPPEDWINDOW
        _USER32.SetWindowLongPtrW(self._bound_hwnd, _GWL_STYLE, fullscreen_style)
        monitor_left, monitor_top, monitor_right, monitor_bottom = (
            info.rcMonitor.left,
            info.rcMonitor.top,
            info.rcMonitor.right,
            info.rcMonitor.bottom,
        )
        _USER32.SetWindowPos(
            self._bound_hwnd,
            _HWND_TOP,
            monitor_left,
            monitor_top,
            monitor_right - monitor_left,
            monitor_bottom - monitor_top,
            _SWP_NOZORDER | _SWP_SHOWWINDOW | _SWP_FRAMECHANGED,
        )
        self._fullscreen = True
        self.fullscreen_changed.emit(True)
        return True

    def restore_fullscreen(self) -> bool:
        if not self._fullscreen or self._bound_hwnd is None or _USER32 is None:
            return False
        if not self.is_window(self._bound_hwnd):
            self._fullscreen = False
            self._original_style = None
            self._original_rect = None
            self.fullscreen_changed.emit(False)
            return False
        if self._original_style is not None:
            _USER32.SetWindowLongPtrW(self._bound_hwnd, _GWL_STYLE, self._original_style)
        if self._original_rect is not None:
            left, top, right, bottom = self._original_rect
            _USER32.SetWindowPos(
                self._bound_hwnd,
                _HWND_TOP,
                left,
                top,
                right - left,
                bottom - top,
                _SWP_NOZORDER | _SWP_SHOWWINDOW | _SWP_FRAMECHANGED,
            )
        self._fullscreen = False
        self._original_style = None
        self._original_rect = None
        self.fullscreen_changed.emit(False)
        return True
