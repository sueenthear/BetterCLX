"""Main Fluent window, navigation and bound-window hotkey scope."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from datetime import datetime

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, FluentWindow, InfoBar, NavigationItemPosition

from better_clx.config import APP_NAME
from better_clx.models import GameWindow
from better_clx.services.settings import SettingsStore
from better_clx.services.monitor import WindowMonitor
from better_clx.services.window_actions import WindowBindingController
from better_clx.ui.about_page import AboutPage
from better_clx.ui.binding_page import BindingPage
from better_clx.ui.combo_page import ComboPage
from better_clx.ui.start_page import StartPage
from better_clx.ui.theme import WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _Message(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _Point),
    ]


class MainWindow(FluentWindow):
    WM_HOTKEY = 0x0312
    VK_F11 = 0x7A

    def __init__(self) -> None:
        # FluentWindow construction can dispatch nativeEvent before subclass setup finishes.
        self._hotkey_registered = False
        self._hotkey_id = 1
        self._user32 = None
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._settings_store = SettingsStore()
        self._app_settings = self._settings_store.load()
        self._restore_geometry()
        self.setMicaEffectEnabled(True)
        self.setWindowIcon(QGuiApplication.instance().windowIcon())

        self.window_controller = WindowBindingController(self)
        self.start_page = StartPage(self)
        self.binding_page = BindingPage(self.window_controller, self)
        self.combo_page = ComboPage(self.window_controller, self)
        self.about_page = AboutPage(self)
        self._init_navigation()

        self.monitor = WindowMonitor(self)
        self.monitor.windows_changed.connect(self._on_windows_changed)
        self.monitor.scan_failed.connect(self._on_scan_failed)
        self.binding_page.refresh_requested.connect(self.monitor.scan)
        self.start_page.binding_requested.connect(lambda: self.switchTo(self.binding_page))
        self._hotkey_registered = False
        self._register_fullscreen_hotkey()
        self.monitor.start()
        # FluentWindow may adjust geometry while interfaces are added; apply the
        # persisted size once more after the complete layout has been built.
        self._restore_geometry()

    def apply_saved_geometry(self) -> None:
        """Reapply persisted geometry after Qt/window-manager layout settles."""
        self._restore_geometry()
        self.updateGeometry()

    def _restore_geometry(self) -> None:
        settings = self._app_settings
        width = max(WINDOW_MIN_WIDTH, int(settings.window_width))
        height = max(WINDOW_MIN_HEIGHT, int(settings.window_height))
        if settings.window_x is None or settings.window_y is None:
            self.resize(width, height)
            return
        self.setGeometry(int(settings.window_x), int(settings.window_y), width, height)
        self._clamp_to_available_screen()

    def _clamp_to_available_screen(self) -> None:
        available = None
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().intersects(self.geometry()):
                available = screen.availableGeometry()
                break
        if available is None:
            available = QGuiApplication.primaryScreen().availableGeometry()
        rect = self.geometry()
        width = min(rect.width(), available.width())
        height = min(rect.height(), available.height())
        x = min(max(rect.x(), available.left()), available.right() - width + 1)
        y = min(max(rect.y(), available.top()), available.bottom() - height + 1)
        self.setGeometry(QRect(x, y, width, height))

    def _save_geometry(self) -> None:
        rect = self.geometry()
        self._app_settings.window_x = rect.x()
        self._app_settings.window_y = rect.y()
        self._app_settings.window_width = max(WINDOW_MIN_WIDTH, rect.width())
        self._app_settings.window_height = max(WINDOW_MIN_HEIGHT, rect.height())
        self._settings_store.save(self._app_settings)

    def _init_navigation(self) -> None:
        self.addSubInterface(
            self.start_page,
            FluentIcon.PLAY,
            "启动",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.binding_page,
            FluentIcon.LINK,
            "绑定",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.combo_page,
            FluentIcon.EDIT,
            "连招",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.about_page,
            FluentIcon.INFO,
            "关于",
            position=NavigationItemPosition.BOTTOM,
        )

    def _register_fullscreen_hotkey(self) -> None:
        if os.name != "nt":
            return
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        self._hotkey_id = 1
        self._user32 = user32
        self._hotkey_registered = bool(
            user32.RegisterHotKey(int(self.winId()), self._hotkey_id, 0, self.VK_F11)
        )

    def _unregister_fullscreen_hotkey(self) -> None:
        if os.name == "nt" and self._hotkey_registered:
            self._user32.UnregisterHotKey(int(self.winId()), self._hotkey_id)
            self._hotkey_registered = False

    def _on_windows_changed(self, windows: list[GameWindow]) -> None:
        self.binding_page.set_windows(windows)
        self.binding_page.set_scan_time(f"最近扫描  {datetime.now():%H:%M:%S}")

    def _on_scan_failed(self, message: str) -> None:
        self.binding_page.set_scan_time("扫描失败")
        InfoBar.error("窗口检测失败", message, parent=self)

    def nativeEvent(self, eventType, message):  # noqa: N802 - Qt API name
        if eventType == "windows_generic_MSG" and self._hotkey_registered:
            msg = ctypes.cast(int(message), ctypes.POINTER(_Message)).contents
            if msg.message == self.WM_HOTKEY and msg.wParam == self._hotkey_id:
                self.window_controller.toggle_fullscreen()
                return True, 0
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self._unregister_fullscreen_hotkey()
        if self.window_controller.is_fullscreen:
            self.window_controller.restore_fullscreen()
        self.combo_page.shutdown()
        self.monitor.stop()
        self._save_geometry()
        super().closeEvent(event)
