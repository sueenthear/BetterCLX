"""Persistence for independent combo-group JSON files and an index file."""

from __future__ import annotations

import json
import os
from pathlib import Path

from better_clx.combo_models import ComboGroup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMBO_DIR = PROJECT_ROOT / "combo"
COMBO_INDEX_PATH = COMBO_DIR / "__all__.json"
LEGACY_COMBO_STORE_PATH = PROJECT_ROOT / "combo_groups.json"


class ComboStore:
    """Store one group per JSON and keep enabled/order metadata in __all__.json."""

    def __init__(self, path: Path | None = None) -> None:
        # Custom paths retain the old single-file behavior for isolated tests/tools.
        self._single_file = path is not None
        self.path = path or COMBO_INDEX_PATH
        self.directory = self.path.parent
        self.index_path = self.path

    def load(self) -> list[ComboGroup]:
        if self._single_file:
            return self._load_single_file()
        if not self.index_path.is_file():
            return self._migrate_legacy()
        try:
            with self.index_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, ValueError, TypeError):
            return []
        entries = payload.get("groups", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            return []
        groups: list[ComboGroup] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            group_id = str(entry.get("group_id") or "")
            if not group_id:
                continue
            group_path = self.directory / f"{group_id}.json"
            group = self._load_group_file(group_path)
            if group is None:
                continue
            # __all__.json owns current ordering/name/enabled state.
            group.name = str(entry.get("name") or group.name)
            group.enabled = bool(entry.get("enabled", group.enabled))
            groups.append(group)
        return groups

    def _load_single_file(self) -> list[ComboGroup]:
        if not self.path.is_file():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, ValueError, TypeError):
            return []
        raw_groups = payload.get("groups", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_groups, list):
            return []
        return [ComboGroup.from_dict(item) for item in raw_groups]

    def save(self, groups: list[ComboGroup]) -> None:
        if self._single_file:
            self._atomic_write(
                self.path,
                {"version": 2, "groups": [group.to_dict() for group in groups]},
            )
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, object]] = []
        active_ids = {group.group_id for group in groups}
        for order, group in enumerate(groups):
            self._write_group_file(group)
            entries.append(
                {
                    "group_id": group.group_id,
                    "name": group.name,
                    "enabled": group.enabled,
                    "order": order,
                    "file": f"{group.group_id}.json",
                }
            )
        # Remove stale group files created by this store, but never touch arbitrary files.
        for group_file in self.directory.glob("*.json"):
            if group_file.name == self.index_path.name:
                continue
            if group_file.stem not in active_ids:
                try:
                    group_file.unlink()
                except OSError:
                    pass
        self._atomic_write(self.index_path, {"version": 2, "groups": entries})

    def _write_group_file(self, group: ComboGroup) -> None:
        self._atomic_write(
            self.directory / f"{group.group_id}.json",
            {"version": 2, "group": group.to_dict()},
        )

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, path)

    @staticmethod
    def _load_group_file(path: Path) -> ComboGroup | None:
        if not path.is_file():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, ValueError, TypeError):
            return None
        raw_group = payload.get("group") if isinstance(payload, dict) else payload
        return ComboGroup.from_dict(raw_group) if isinstance(raw_group, dict) else None

    def _migrate_legacy(self) -> list[ComboGroup]:
        legacy_path = LEGACY_COMBO_STORE_PATH
        if self.index_path != COMBO_INDEX_PATH and self.index_path.is_file():
            legacy_path = self.index_path
        if not legacy_path.is_file():
            return []
        try:
            with legacy_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, ValueError, TypeError):
            return []
        raw_groups = payload.get("groups", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_groups, list):
            return []
        groups = [ComboGroup.from_dict(item) for item in raw_groups]
        self.save(groups)
        return groups

    @staticmethod
    def export_group(group: ComboGroup, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 2, "group": group.to_dict()}
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")

    @staticmethod
    def import_group(path: Path) -> ComboGroup:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, dict) and isinstance(payload.get("group"), dict):
            raw_group = payload["group"]
        elif isinstance(payload, dict) and isinstance(payload.get("groups"), list):
            groups = payload["groups"]
            if not groups:
                raise ValueError("连招文件中没有连招组")
            raw_group = groups[0]
        elif isinstance(payload, dict):
            raw_group = payload
        else:
            raise ValueError("连招文件格式无效")
        return ComboGroup.from_dict(raw_group, new_id=True)
