"""Tests for the combo trigger state machine (bind/ordering/hold/toggle)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from better_clx.combo_models import ComboGroup, ComboOperation, ComboTrigger, OperationType, TriggerMode
from better_clx.services.combo_runtime import ComboRuntime
from better_clx.services.window_actions import WindowBindingController


class FakeInput:
    """Deterministic input backend: keys are set by the test, sends are recorded."""

    def __init__(self) -> None:
        self.down: set[str] = set()
        self.sent: list[tuple[int, str, str]] = []
        self.scrolls: list[tuple[int, str]] = []

    def is_window(self, hwnd: int | None) -> bool:
        return bool(hwnd)

    def is_key_down(self, key_name: str) -> bool:
        return key_name in self.down

    def send_key(self, hwnd: int | None, key_name: str, action: str) -> bool:
        self.sent.append((int(hwnd or 0), key_name, action))
        return True

    def send_scroll(self, hwnd: int | None, direction: str) -> bool:
        self.scrolls.append((int(hwnd or 0), direction))
        return True

    def release_all(self, hwnd: int | None) -> None:
        return


def hold_group(operations: list[ComboOperation], trigger: str = "Q") -> ComboGroup:
    return ComboGroup(
        name="按住组",
        enabled=True,
        triggers=[ComboTrigger(key_name=trigger, mode=TriggerMode.HOLD.value)],
        operations=operations,
    )


def toggle_group(operations: list[ComboOperation], trigger: str = "T") -> ComboGroup:
    return ComboGroup(
        name="切换组",
        enabled=True,
        triggers=[ComboTrigger(key_name=trigger, mode=TriggerMode.TOGGLE.value)],
        operations=operations,
    )


class ComboRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def _runtime(self) -> tuple[ComboRuntime, FakeInput, WindowBindingController]:
        controller = WindowBindingController()
        controller._bound_hwnd = 0x2000
        backend = FakeInput()
        runtime = ComboRuntime(controller, input_backend=backend)
        return runtime, backend, controller

    def test_hold_trigger_runs_operations_top_to_bottom(self) -> None:
        runtime, backend, _ = self._runtime()
        operations = [
            ComboOperation(key_name="1"),
            ComboOperation(key_name="2"),
            ComboOperation(key_name="3"),
        ]
        runtime.set_groups([hold_group(operations)])
        backend.down = {"Q"}
        runtime.tick()
        self.assertEqual([item[1] for item in backend.sent], ["1"])
        runtime.tick()
        self.assertEqual([item[1] for item in backend.sent], ["1", "2"])
        runtime.tick()
        self.assertEqual([item[1] for item in backend.sent], ["1", "2", "3"])
        self.assertTrue(all(action == "press" for _, _, action in backend.sent))
        self.assertTrue(all(hwnd == 0x2000 for hwnd, _, _ in backend.sent))

    def test_hold_release_stops_and_releases_pressed_keys(self) -> None:
        runtime, backend, _ = self._runtime()
        runtime.set_groups([hold_group([ComboOperation(key_name="1")])])
        backend.down = {"Q"}
        runtime.tick()
        self.assertEqual(backend.sent, [(0x2000, "1", "press")])
        backend.down = set()
        runtime.tick()
        self.assertEqual(backend.sent[-1], (0x2000, "1", "release"))

    def test_toggle_second_press_terminates(self) -> None:
        runtime, backend, _ = self._runtime()
        runtime.set_groups([toggle_group([ComboOperation(key_name="9")])])
        backend.down = {"T"}
        runtime.tick()
        backend.down = set()
        runtime.tick()
        self.assertEqual(backend.sent, [(0x2000, "9", "press")])
        backend.down = {"T"}
        runtime.tick()
        backend.down = set()
        runtime.tick()
        self.assertEqual(backend.sent[-1], (0x2000, "9", "release"))

    def test_toggle_group_uses_only_group_trigger_keys(self) -> None:
        runtime, backend, _ = self._runtime()
        group = toggle_group([ComboOperation(key_name="A")], trigger="T")
        runtime.set_groups([group])
        backend.down = {"Q"}
        runtime.tick()
        self.assertFalse(runtime._states[group.group_id].running)
        backend.down = {"T"}
        runtime.tick()
        self.assertTrue(runtime._states[group.group_id].running)
        backend.down = set()
        runtime.tick()
        self.assertTrue(runtime._states[group.group_id].running)

    def test_delay_gate_blocks_until_deadline(self) -> None:
        runtime, backend, _ = self._runtime()
        operations = [ComboOperation(key_name="1"), ComboOperation(operation_type=OperationType.DELAY.value, delay_ms=500), ComboOperation(key_name="2")]
        runtime.set_groups([hold_group(operations)])
        backend.down = {"Q"}
        with patch("better_clx.services.combo_runtime.time.monotonic", return_value=100.0):
            runtime.tick()
            runtime.tick()
            runtime.tick()
        self.assertEqual([item[1] for item in backend.sent], ["1"])
        with patch("better_clx.services.combo_runtime.time.monotonic", return_value=100.1):
            runtime.tick()
        self.assertEqual([item[1] for item in backend.sent], ["1"])
        with patch("better_clx.services.combo_runtime.time.monotonic", return_value=100.6):
            runtime.tick()
        self.assertEqual([item[1] for item in backend.sent], ["1", "2"])

    def test_disabled_group_never_triggers(self) -> None:
        runtime, backend, _ = self._runtime()
        group = hold_group([ComboOperation(key_name="1")])
        group.enabled = False
        runtime.set_groups([group])
        backend.down = {"Q"}
        runtime.tick()
        runtime.tick()
        self.assertEqual(backend.sent, [])

    def test_mouse_scroll_operation_targets_bound_hwnd(self) -> None:
        runtime, backend, _ = self._runtime()
        scroll = ComboOperation(operation_type=OperationType.MOUSE_SCROLL.value, scroll_direction="down")
        runtime.set_groups([hold_group([scroll])])
        backend.down = {"Q"}
        runtime.tick()
        self.assertEqual(backend.scrolls, [(0x2000, "down")])

    def test_no_bound_window_sends_nothing(self) -> None:
        controller = WindowBindingController()
        backend = FakeInput()
        runtime = ComboRuntime(controller, input_backend=backend)
        runtime.set_groups([hold_group([ComboOperation(key_name="1")])])
        backend.down = {"Q"}
        runtime.tick()
        self.assertEqual(backend.sent, [])

    def test_unbind_releases_keys_held_by_running_group(self) -> None:
        runtime, backend, controller = self._runtime()
        runtime.set_groups([hold_group([ComboOperation(key_name="1")])])
        backend.down = {"Q"}
        runtime.tick()
        self.assertEqual(backend.sent, [(0x2000, "1", "press")])
        controller._bound_hwnd = None
        runtime.tick()
        self.assertIn((0x2000, "1", "release"), backend.sent)


if __name__ == "__main__":
    unittest.main()