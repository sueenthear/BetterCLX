"""Tests for combo group models, persistence and Win32 key mapping."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from better_clx.combo_models import ComboGroup, ComboOperation, ComboTrigger, OperationType, TriggerMode
from better_clx.combo_store import ComboStore
from better_clx.services.win32_input import Win32Input, key_to_vk, normalize_key_name, qt_key_name


class ComboDataTests(unittest.TestCase):
    def test_group_and_operations_round_trip(self) -> None:
        group = ComboGroup(
            name="测试连招",
            enabled=True,
            triggers=[
                ComboTrigger(key_name="Q", mode=TriggerMode.TOGGLE.value),
                ComboTrigger(key_name="E", mode=TriggerMode.HOLD.value),
            ],
            operations=[
                ComboOperation(
                    operation_type=OperationType.KEYBOARD.value,
                    key_name="1",
                ),
                ComboOperation(operation_type=OperationType.DELAY.value, delay_ms=250),
                ComboOperation(operation_type=OperationType.MOUSE_SCROLL.value, scroll_direction="down"),
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ComboStore(Path(temp_dir) / "combo_groups.json")
            store.save([group])
            loaded = store.load()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].to_dict(), group.to_dict())
        self.assertEqual(
            [(trigger.key_name, trigger.mode) for trigger in loaded[0].triggers],
            [("Q", TriggerMode.TOGGLE.value), ("E", TriggerMode.HOLD.value)],
        )

    def test_imported_group_gets_a_fresh_id(self) -> None:
        group = ComboGroup(name="共享", operations=[ComboOperation(key_name="R")])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shared.combo.json"
            ComboStore.export_group(group, path)
            imported = ComboStore.import_group(path)
        self.assertNotEqual(imported.group_id, group.group_id)
        self.assertEqual(imported.name, group.name)
        self.assertEqual(imported.operations[0].key_name, "R")

    def test_invalid_import_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                ComboStore.import_group(path)

    def test_key_name_mapping_and_normalization(self) -> None:
        self.assertEqual(key_to_vk("a"), ord("A"))
        self.assertEqual(key_to_vk("f11"), 0x7A)
        self.assertEqual(key_to_vk("CONTROL"), key_to_vk("CTRL"))
        self.assertEqual(normalize_key_name(" page up "), "PAGEUP")
        self.assertEqual(Win32Input().validate_keys(["A", "F2", "UNKNOWN_KEY"]), ["A", "F2"])

    def test_qt_key_capture_maps_special_and_printable_keys(self) -> None:
        from PySide6.QtCore import Qt

        self.assertEqual(qt_key_name(Qt.Key.Key_A, "a"), "A")
        self.assertEqual(qt_key_name(Qt.Key.Key_F5), "F5")
        self.assertEqual(qt_key_name(Qt.Key.Key_Space, " "), "SPACE")

    def test_key_output_is_sent_only_to_given_hwnd(self) -> None:
        input_backend = Win32Input()
        with (
            patch("better_clx.services.win32_input.win32gui.IsWindow", return_value=True),
            patch("better_clx.services.win32_input.win32api.PostMessage") as post_message,
        ):
            self.assertTrue(input_backend.send_key(0x1234, "A", "press"))
        self.assertEqual(post_message.call_args.args[0], 0x1234)


if __name__ == "__main__":
    unittest.main()
