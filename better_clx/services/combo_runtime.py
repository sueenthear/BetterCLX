"""支持多个独立触发器的连招运行时。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal

from better_clx.combo_models import ComboGroup, ComboOperation, KeyboardAction, OperationType, TriggerMode
from better_clx.services.win32_input import Win32Input
from better_clx.services.window_actions import WindowBindingController


@dataclass(slots=True)
class _TriggerState:
    previous_down: bool = False
    toggle_active: bool = False
    hold_active: bool = False


@dataclass(slots=True)
class _GroupState:
    triggers: dict[str, _TriggerState] = field(default_factory=dict)
    running: bool = False
    next_operation: int = 0
    deadline: float = 0.0
    output_hwnd: int | None = None
    held_output_keys: set[str] = field(default_factory=set)


class ComboRuntime(QObject):
    status_changed = Signal(str)
    group_running_changed = Signal(str, bool)
    POLL_INTERVAL_MS = 20

    def __init__(self, controller: WindowBindingController, parent=None, input_backend=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.input = input_backend or Win32Input()
        self.groups: list[ComboGroup] = []
        self.enabled = True
        self._states: dict[str, _GroupState] = {}
        self._key_owners: dict[tuple[int, str], set[str]] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.tick)
        self.controller.bound_changed.connect(self._on_bound_changed)

    def set_groups(self, groups: list[ComboGroup]) -> None:
        self.release_all()
        self.groups = groups
        self._states = {
            group.group_id: _GroupState(
                triggers={trigger.trigger_id: _TriggerState() for trigger in group.triggers}
            )
            for group in groups
        }

    def start(self) -> None:
        self._timer.start()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            self.release_all()
        self.status_changed.emit("连招总开关：已开启" if self.enabled else "连招总开关：已关闭")

    def stop(self) -> None:
        self._timer.stop()
        self.release_all()

    def release_all(self) -> None:
        for group_id, state in self._states.items():
            self._release_group_keys(group_id, state)
            for trigger_state in state.triggers.values():
                trigger_state.previous_down = False
                trigger_state.toggle_active = False
                trigger_state.hold_active = False
            state.running = False
            state.next_operation = 0
            state.deadline = 0.0
        for (hwnd, key), owners in tuple(self._key_owners.items()):
            if owners:
                self.input.send_key(hwnd, key, KeyboardAction.RELEASE.value)
        self._key_owners.clear()

    def _on_bound_changed(self, _hwnd) -> None:
        self.release_all()

    def tick(self) -> None:
        if not self.enabled:
            return
        hwnd = self.controller.bound_hwnd
        if not hwnd or not self.input.is_window(hwnd):
            self.release_all()
            return
        now = time.monotonic()
        for group in tuple(self.groups):
            state = self._states.setdefault(group.group_id, _GroupState())
            if not group.enabled:
                self._stop_group(group, state)
                continue
            self._poll_group_triggers(group, state)
            if state.running:
                self._advance_sequence(group, state, hwnd, now)

    def _poll_group_triggers(self, group: ComboGroup, state: _GroupState) -> None:
        state.triggers = {
            trigger.trigger_id: state.triggers.get(trigger.trigger_id, _TriggerState())
            for trigger in group.triggers
        }
        for trigger in group.triggers:
            trigger_state = state.triggers[trigger.trigger_id]
            is_down = bool(trigger.key_name and self.input.is_key_down(trigger.key_name))
            rising = is_down and not trigger_state.previous_down
            falling = trigger_state.previous_down and not is_down
            trigger_state.previous_down = is_down
            if trigger.mode == TriggerMode.TOGGLE.value:
                if rising:
                    trigger_state.toggle_active = not trigger_state.toggle_active
            else:
                if falling:
                    trigger_state.hold_active = False
                if rising:
                    trigger_state.hold_active = True

        active = any(
            trigger_state.toggle_active or trigger_state.hold_active
            for trigger_state in state.triggers.values()
        )
        if active:
            self._start_group(group, state, self.controller.bound_hwnd)
        elif state.running:
            self._stop_group(group, state)

    def _start_group(self, group: ComboGroup, state: _GroupState, hwnd: int | None) -> None:
        if state.running or not group.operations or not hwnd:
            return
        state.running = True
        state.output_hwnd = hwnd
        state.next_operation = 0
        state.deadline = 0.0
        self.status_changed.emit(f"{group.name} · 已触发")

    def _advance_sequence(self, group: ComboGroup, state: _GroupState, hwnd: int, now: float) -> None:
        if not any(s.toggle_active or s.hold_active for s in state.triggers.values()):
            self._stop_group(group, state)
            return
        if state.deadline and now < state.deadline:
            return
        state.deadline = 0.0
        if state.next_operation >= len(group.operations):
            state.next_operation = 0
        operation = group.operations[state.next_operation]
        state.next_operation += 1
        self._execute_operation(group.group_id, operation, state, hwnd, now)

    def _execute_operation(self, group_id: str, operation: ComboOperation, state: _GroupState, hwnd: int, now: float) -> None:
        if operation.operation_type == OperationType.KEYBOARD.value and operation.key_name:
            if operation.keyboard_action == KeyboardAction.PRESS.value:
                self._press_key(group_id, state, hwnd, operation.key_name)
            else:
                self._release_key(group_id, state, hwnd, operation.key_name)
        elif operation.operation_type == OperationType.MOUSE_SCROLL.value:
            self.input.send_scroll(hwnd, operation.scroll_direction)
        elif operation.operation_type == OperationType.DELAY.value:
            state.deadline = now + max(0, operation.delay_ms) / 1000

    def _press_key(self, group_id: str, state: _GroupState, hwnd: int, key: str) -> None:
        owners = self._key_owners.setdefault((hwnd, key), set())
        sent = True
        if not owners:
            sent = bool(self.input.send_key(hwnd, key, KeyboardAction.PRESS.value))
        owners.add(group_id)
        state.held_output_keys.add(key)

    def _release_key(self, group_id: str, state: _GroupState, hwnd: int, key: str) -> None:
        owners = self._key_owners.get((hwnd, key))
        if owners is None:
            return
        owners.discard(group_id)
        if not owners:
            self.input.send_key(hwnd, key, KeyboardAction.RELEASE.value)
            self._key_owners.pop((hwnd, key), None)
        state.held_output_keys.discard(key)

    def _release_group_keys(self, group_id: str, state: _GroupState) -> None:
        if state.output_hwnd is not None:
            for key in tuple(state.held_output_keys):
                self._release_key(group_id, state, state.output_hwnd, key)
        state.held_output_keys.clear()
        state.output_hwnd = None

    def _stop_group(self, group: ComboGroup, state: _GroupState) -> None:
        if not state.running and not state.held_output_keys:
            return
        self._release_group_keys(group.group_id, state)
        state.running = False
        state.next_operation = 0
        state.deadline = 0.0
        self.status_changed.emit(f"{group.name} · 已停止")
