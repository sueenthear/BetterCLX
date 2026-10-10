"""Runtime paths shared by source and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
IS_FROZEN = bool(getattr(sys, "frozen", False))
INSTALL_ROOT = Path(sys.executable).resolve().parent if IS_FROZEN else SOURCE_ROOT
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", INSTALL_ROOT))


def install_root() -> Path:
    """Return the directory that owns the executable and user data."""
    return INSTALL_ROOT


def resource_path(relative_path: str | Path) -> Path:
    """Resolve bundled read-only resources in source and onedir layouts."""
    relative = Path(relative_path)
    candidates = [BUNDLE_ROOT / relative, INSTALL_ROOT / relative, SOURCE_ROOT / relative]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def is_frozen() -> bool:
    return IS_FROZEN
