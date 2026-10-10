"""Tests for independent hold/toggle triggers in one combo group."""

from __future__ import annotations

import unittest

from PySide6.QtCore import QCoreApplication

from better_clx.combo_models import ComboGroup, ComboOperation, ComboTrigger, TriggerMode
from better_clx.services.combo_runtime import ComboRuntime
from better_clx.services.win32_input import key_to_vk
from better_clx.services.window_actions import WindowBindingController


class FakeInput:
    def __init__(self) -> None:
        self.down: set[str] = set()
        self.sent: list[tuple[int, str, str]] = []

    def is_window(self, hwnd: int | None) -> bool:
        return bool(hwnd)

    def is_key_down(self, key_name: str) -> bool:
        return key_name in self.down

    def send_key(self, hwnd: int | None, key_name: str, action: str) -> bool:
        self.sent.append((int(hwnd or 0), key_name, action))
        return True

    def send_scroll(self, hwnd: int | None, direction: str) -> bool:
        return True

    def release_all(self, hwnd: int | None) -> None:
        return


class MultiTriggerTests(unittest.TestCase):
    def test_mouse_button_trigger_names_map_to_win32_virtual_keys(self) -> None:
        self.assertIsNotNone(key_to_vk("鼠标左键"))
        self.assertIsNotNone(key_to_vk("鼠标右键"))
        self.assertIsNotNone(key_to_vk("鼠标中键"))

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_q_toggle_and_e_hold_can_coexist(self) -> None:
        controller = WindowBindingController()
        controller._bound_hwnd = 0x2000
        backend = FakeInput()
        runtime = ComboRuntime(controller, input_backend=backend)
        group = ComboGroup(
            name="混合触发",
            enabled=True,
            triggers=[
                ComboTrigger(key_name="Q", mode=TriggerMode.TOGGLE.value),
                ComboTrigger(key_name="E", mode=TriggerMode.HOLD.value),
            ],
            operations=[ComboOperation(key_name="1")],
        )
        runtime.set_groups([group])

        # Q toggles the group on and remains active after release.
        backend.down = {"Q"}
        runtime.tick()
        backend.down = set()
        runtime.tick()
        state = runtime._states[group.group_id]
        self.assertTrue(state.running)
        self.assertTrue(state.triggers[group.triggers[0].trigger_id].toggle_active)

        # E can be held at the same time without cancelling Q.
        backend.down = {"E"}
        runtime.tick()
        self.assertTrue(state.running)
        self.assertTrue(state.triggers[group.triggers[1].trigger_id].hold_active)

        # Releasing E leaves Q's toggle active.
        backend.down = set()
        runtime.tick()
        self.assertTrue(state.running)
        self.assertTrue(state.triggers[group.triggers[0].trigger_id].toggle_active)
        self.assertFalse(state.triggers[group.triggers[1].trigger_id].hold_active)

        # Q again turns the group off.
        backend.down = {"Q"}
        runtime.tick()
        backend.down = set()
        runtime.tick()
        self.assertFalse(state.running)

    def test_multiple_trigger_rows_round_trip(self) -> None:
        group = ComboGroup(
            triggers=[
                ComboTrigger(key_name="Q", mode=TriggerMode.TOGGLE.value),
                ComboTrigger(key_name="E", mode=TriggerMode.HOLD.value),
            ]
        )
        restored = ComboGroup.from_dict(group.to_dict())
        self.assertEqual(
            [(trigger.key_name, trigger.mode) for trigger in restored.triggers],
            [("Q", "toggle"), ("E", "hold")],
        )


if __name__ == "__main__":
    unittest.main()
