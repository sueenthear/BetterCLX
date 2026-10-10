"""Domain models used by the detector and UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WindowStatus(StrEnum):
    RUNNING = "运行中"
    LOGGING_IN = "登录中"


@dataclass(frozen=True, slots=True)
class GameWindow:
    hwnd: int
    pid: int
    title: str
    process_name: str
    client_width: int
    client_height: int
    login_hwnd: int | None = None

    @property
    def status(self) -> WindowStatus:
        return WindowStatus.LOGGING_IN if self.login_hwnd else WindowStatus.RUNNING

    @property
    def status_detail(self) -> str:
        if self.login_hwnd:
            return f"检测到登录窗口 · HWND 0x{self.login_hwnd:X}"
        return "未检测到归属登录窗口"
