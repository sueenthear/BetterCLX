"""连招组、独立触发器与动作的持久化模型。"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class TriggerMode(StrEnum):
    HOLD = "hold"
    TOGGLE = "toggle"

    @property
    def label(self) -> str:
        return "按住" if self is TriggerMode.HOLD else "切换"


class OperationType(StrEnum):
    KEYBOARD = "keyboard"
    DELAY = "delay"
    MOUSE_SCROLL = "mouse_scroll"

    @property
    def label(self) -> str:
        return {
            OperationType.KEYBOARD: "键盘事件",
            OperationType.DELAY: "延时事件",
            OperationType.MOUSE_SCROLL: "鼠标事件",
        }[self]


class KeyboardAction(StrEnum):
    PRESS = "press"
    RELEASE = "release"


class ScrollDirection(StrEnum):
    UP = "up"
    DOWN = "down"


@dataclass(slots=True)
class ComboTrigger:
    """One global trigger key with its own independent mode."""

    trigger_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    key_name: str = ""
    mode: str = TriggerMode.HOLD.value

    @classmethod
    def from_dict(cls, data: object) -> "ComboTrigger":
        if not isinstance(data, dict):
            return cls()
        mode = str(data.get("mode") or data.get("trigger_mode") or TriggerMode.HOLD.value)
        if mode not in {item.value for item in TriggerMode}:
            mode = TriggerMode.HOLD.value
        return cls(
            trigger_id=str(data.get("trigger_id") or uuid.uuid4().hex),
            key_name=str(data.get("key_name") or data.get("key") or ""),
            mode=mode,
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class ComboOperation:
    operation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    operation_type: str = OperationType.KEYBOARD.value
    key_name: str = ""
    keyboard_action: str = KeyboardAction.PRESS.value
    delay_ms: int = 100
    delay_value: float | None = None
    delay_unit: str = "ms"
    scroll_direction: str = ScrollDirection.UP.value

    def __post_init__(self) -> None:
        if self.delay_value is None:
            self.delay_value = self.delay_ms / 1000.0 if self.delay_unit == "s" else float(self.delay_ms)

    @classmethod
    def from_dict(cls, data: object) -> "ComboOperation":
        if not isinstance(data, dict):
            return cls()
        operation_type = str(data.get("operation_type") or OperationType.KEYBOARD.value)
        if operation_type not in {item.value for item in OperationType}:
            operation_type = OperationType.KEYBOARD.value
        action = str(data.get("keyboard_action") or KeyboardAction.PRESS.value)
        if action not in {item.value for item in KeyboardAction}:
            action = KeyboardAction.PRESS.value
        direction = str(data.get("scroll_direction") or ScrollDirection.UP.value)
        if direction not in {item.value for item in ScrollDirection}:
            direction = ScrollDirection.UP.value
        unit = str(data.get("delay_unit") or "ms").lower()
        if unit not in {"ms", "s"}:
            unit = "ms"
        try:
            if "delay_value" in data:
                value = max(0.0, min(3_600.0, float(data.get("delay_value", 100))))
            else:
                value = max(0.0, min(3_600_000.0, float(data.get("delay_ms", 100))))
                unit = "ms"
        except (TypeError, ValueError):
            value = 100.0
            unit = "ms"
        delay_ms = round(value * 1000 if unit == "s" else value)
        return cls(
            operation_id=str(data.get("operation_id") or uuid.uuid4().hex),
            operation_type=operation_type,
            key_name=str(data.get("key_name") or ""),
            keyboard_action=action,
            delay_ms=delay_ms,
            delay_value=value,
            delay_unit=unit,
            scroll_direction=direction,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ComboGroup:
    group_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "新连招组"
    enabled: bool = False
    triggers: list[ComboTrigger] = field(default_factory=list)
    operations: list[ComboOperation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: object, new_id: bool = False) -> "ComboGroup":
        if not isinstance(data, dict):
            return cls()
        raw_triggers = data.get("triggers")
        if isinstance(raw_triggers, list):
            triggers = [ComboTrigger.from_dict(item) for item in raw_triggers]
        else:
            # Migrate the previous group-level trigger_keys + trigger_mode format.
            legacy_keys = data.get("trigger_keys", [])
            mode = str(data.get("trigger_mode") or TriggerMode.HOLD.value)
            triggers = [ComboTrigger(key_name=str(key), mode=mode) for key in legacy_keys if str(key).strip()]
        raw_operations = data.get("operations", [])
        operations = [ComboOperation.from_dict(item) for item in raw_operations] if isinstance(raw_operations, list) else []
        return cls(
            group_id=uuid.uuid4().hex if new_id else str(data.get("group_id") or uuid.uuid4().hex),
            name=str(data.get("name") or "新连招组"),
            enabled=bool(data.get("enabled", False)),
            triggers=triggers,
            operations=operations,
        )

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["triggers"] = [trigger.to_dict() for trigger in self.triggers]
        data["operations"] = [operation.to_dict() for operation in self.operations]
        return data
