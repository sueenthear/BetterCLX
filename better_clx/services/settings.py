"""Persistent application settings for game and script launchers."""

from __future__ import annotations

import configparser
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from better_clx.config import GAME_PROCESS_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PROJECT_ROOT / "user_setting.json"
LEGACY_SETTINGS_PATH = PROJECT_ROOT / "user_setting.ini"

DEFAULT_GAME_64_RELATIVE_PATH = r"Engine\Binaries\Win64\wyclx64.exe"
DEFAULT_GAME_32_RELATIVE_PATH = r"Engine\Binaries\Win32\wyclx.exe"
DEFAULT_GAME_LAUNCH_RELATIVE_PATH = "Launcher.exe"


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class ScriptConfig:
    """One independently configurable script launcher."""

    name: str = "新脚本"
    path: str = ""
    update_url: str = ""
    script_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @classmethod
    def from_dict(cls, data: object) -> "ScriptConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            name=str(data.get("name") or "新脚本"),
            path=str(data.get("path") or ""),
            update_url=str(data.get("update_url") or ""),
            script_id=str(data.get("script_id") or uuid.uuid4().hex),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class AppSettings:
    """All user-editable launcher settings."""

    game_path: str = ""
    game_version: str = "auto"
    search_timeout: int = 10
    game_64_relative_path: str = DEFAULT_GAME_64_RELATIVE_PATH
    game_32_relative_path: str = DEFAULT_GAME_32_RELATIVE_PATH
    game_launch_relative_path: str = DEFAULT_GAME_LAUNCH_RELATIVE_PATH
    window_x: int | None = None
    window_y: int | None = None
    window_width: int = 1080
    window_height: int = 720
    scripts: list[ScriptConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["scripts"] = [script.to_dict() for script in self.scripts]
        return data

    @classmethod
    def from_dict(cls, data: object) -> "AppSettings":
        if not isinstance(data, dict):
            return cls()
        try:
            timeout = max(1, int(data.get("search_timeout", 10)))
        except (TypeError, ValueError):
            timeout = 10
        scripts_data = data.get("scripts", [])
        scripts = [ScriptConfig.from_dict(item) for item in scripts_data] if isinstance(scripts_data, list) else []
        version = str(data.get("game_version") or "auto")
        if version not in {"64", "32", "auto"}:
            version = "auto"
        return cls(
            game_path=str(data.get("game_path") or ""),
            game_version=version,
            search_timeout=timeout,
            game_64_relative_path=str(data.get("game_64_relative_path") or DEFAULT_GAME_64_RELATIVE_PATH),
            game_32_relative_path=str(data.get("game_32_relative_path") or DEFAULT_GAME_32_RELATIVE_PATH),
            game_launch_relative_path=str(data.get("game_launch_relative_path") or DEFAULT_GAME_LAUNCH_RELATIVE_PATH),
            window_x=_optional_int(data.get("window_x")),
            window_y=_optional_int(data.get("window_y")),
            window_width=max(640, _safe_int(data.get("window_width"), 1080)),
            window_height=max(480, _safe_int(data.get("window_height"), 720)),
            scripts=scripts,
        )


class SettingsStore:
    """Load and save settings without coupling persistence to the UI."""

    def __init__(self, path: Path | None = None, legacy_path: Path | None = None) -> None:
        self.path = path or SETTINGS_PATH
        self.legacy_path = legacy_path or LEGACY_SETTINGS_PATH

    def load(self) -> AppSettings:
        if self.path.is_file():
            try:
                with self.path.open("r", encoding="utf-8") as file:
                    return AppSettings.from_dict(json.load(file))
            except (OSError, ValueError, TypeError):
                pass

        settings = self._load_legacy()
        if settings is not None:
            self.save(settings)
            return settings
        return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(settings.to_dict(), file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, self.path)

    def _load_legacy(self) -> AppSettings | None:
        if not self.legacy_path.is_file():
            return None
        parser = configparser.ConfigParser()
        try:
            parser.read(self.legacy_path, encoding="utf-8")
        except (OSError, UnicodeError):
            return None

        game_path = parser.get("Path", "game_path", fallback="").strip().strip('"')
        version = parser.get("last_save", "version_choice", fallback="auto").strip().lower()
        if version not in {"64", "32", "auto"}:
            version = "auto"
        scripts: list[ScriptConfig] = []
        script_path = parser.get("Path", "tool_path", fallback="").strip().strip('"')
        update_url = parser.get("web", "url", fallback="").strip().strip('"')
        if script_path:
            scripts.append(
                ScriptConfig(
                    name=Path(script_path).stem or "旧版脚本",
                    path=script_path,
                    update_url=update_url,
                )
            )
        return AppSettings(
            game_path=game_path,
            game_version=version,
            search_timeout=parser.getint("setting", "search_timeout", fallback=10),
            game_64_relative_path=parser.get("Path", "64x_relative_path", fallback=DEFAULT_GAME_64_RELATIVE_PATH),
            game_32_relative_path=parser.get("Path", "32x_relative_path", fallback=DEFAULT_GAME_32_RELATIVE_PATH),
            game_launch_relative_path=parser.get("Path", "launch_path", fallback=DEFAULT_GAME_LAUNCH_RELATIVE_PATH),
            scripts=scripts,
        )


# Keep these names easy to discover for callers that need the defaults.
SUPPORTED_GAME_PROCESS_NAMES = GAME_PROCESS_NAMES
