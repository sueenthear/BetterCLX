"""Periodic game window monitoring service."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from better_clx.config import MONITOR_INTERVAL_MS
from better_clx.models import GameWindow
from better_clx.platform.windows import detect_game_windows


class WindowMonitor(QObject):
    """Poll Win32 windows without putting detection logic in the UI."""

    windows_changed = Signal(list)
    scan_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(MONITOR_INTERVAL_MS)
        self._timer.timeout.connect(self.scan)

    def start(self) -> None:
        self.scan()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def scan(self) -> None:
        try:
            self.windows_changed.emit(detect_game_windows())
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.scan_failed.emit(str(exc))
