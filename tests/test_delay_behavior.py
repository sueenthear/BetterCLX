"""Delay value persistence and runtime deadline tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from better_clx.combo_models import ComboGroup, ComboOperation, ComboTrigger, OperationType, TriggerMode
from better_clx.combo_store import ComboStore
from better_clx.services.combo_runtime import ComboRuntime
from better_clx.services.window_actions import WindowBindingController


class _Input:
    def __init__(self) -> None:
        self.down = {"Q"}
        self.sent = []

    def is_window(self, hwnd):
        return bool(hwnd)

    def is_key_down(self, key):
        return key in self.down

    def send_key(self, hwnd, key, action):
        self.sent.append((hwnd, key, action))
        return True

    def send_scroll(self, hwnd, direction):
        return True

    def release_all(self, hwnd):
        return None


class DelayBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_delay_ms_round_trips_in_combo_file(self):
        group = ComboGroup(
            triggers=[ComboTrigger(key_name="Q", mode=TriggerMode.HOLD.value)],
            operations=[ComboOperation(operation_type=OperationType.DELAY.value, delay_ms=1500, delay_value=1.5, delay_unit="s")],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "combo_groups.json"
            store = ComboStore(path)
            store.save([group])
            loaded = store.load()
        self.assertEqual(loaded[0].operations[0].delay_ms, 1500)
        self.assertEqual(loaded[0].operations[0].delay_value, 1.5)
        self.assertEqual(loaded[0].operations[0].delay_unit, "s")

    def test_runtime_waits_for_delay_deadline(self):
        controller = WindowBindingController()
        controller._bound_hwnd = 0x2000
        backend = _Input()
        runtime = ComboRuntime(controller, input_backend=backend)
        group = ComboGroup(
            enabled=True,
            triggers=[ComboTrigger(key_name="Q", mode=TriggerMode.HOLD.value)],
            operations=[
                ComboOperation(operation_type=OperationType.DELAY.value, delay_ms=1000),
                ComboOperation(key_name="1"),
            ],
        )
        runtime.set_groups([group])
        with patch("better_clx.services.combo_runtime.time.monotonic", return_value=10.0):
            runtime.tick()
        with patch("better_clx.services.combo_runtime.time.monotonic", return_value=10.5):
            runtime.tick()
        self.assertEqual(backend.sent, [])
        with patch("better_clx.services.combo_runtime.time.monotonic", return_value=11.1):
            runtime.tick()
        self.assertEqual(backend.sent, [(0x2000, "1", "press")])


if __name__ == "__main__":
    unittest.main()
