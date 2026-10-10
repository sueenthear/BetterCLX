"""Application configuration and constants."""

from __future__ import annotations

APP_NAME = "Better CLX"
APP_VERSION = "0.1.0"

GAME_PROCESS_NAMES = frozenset({"wyclx64.exe", "wyclx.exe"})
GAME_TITLE_KEYWORDS = ("一梦江湖",)
LOGIN_WINDOW_CLASSES = frozenset({"MPAY_LOGIN"})
LOGIN_TITLE_KEYWORDS = ("登录",)
MONITOR_INTERVAL_MS = 1000
