"""Offscreen UI smoke tests for the two-column combo editor."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from better_clx.ui.combo_editor import KeyListenButton  # noqa: E402
from better_clx.combo_models import OperationType  # noqa: E402
from better_clx.combo_store import ComboStore  # noqa: E402
from better_clx.services.window_actions import WindowBindingController  # noqa: E402
from better_clx.ui.combo_page import ComboPage  # noqa: E402


class ComboEditorUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self._temp_dir.name) / "combo_groups.json"
        self.store = ComboStore(self.store_path)
        self.controller = WindowBindingController()
        self.page = ComboPage(self.controller, store=self.store)

    def tearDown(self) -> None:
        self.page.runtime.stop()
        self.page.deleteLater()
        self._temp_dir.cleanup()

    def test_new_group_appears_in_left_list_and_persists(self) -> None:
        self.page.add_empty_group()
        self.assertEqual(self.page.group_list.count(), 1)
        self.assertEqual(len(self.page.groups), 1)
        self.assertTrue(self.store_path.is_file())

    def test_adding_each_operation_type_updates_editor_list(self) -> None:
        self.page.add_empty_group()
        # index 1 = keyboard, 2 = delay, 3 = mouse scroll
        for index in (1, 2, 3):
            self.page._add_operation_from_menu(index)
        types = [operation.operation_type for operation in self.page.groups[0].operations]
        self.assertEqual(
            types,
            [OperationType.KEYBOARD.value, OperationType.DELAY.value, OperationType.MOUSE_SCROLL.value],
        )
        self.assertEqual(self.page.operation_list.count(), 3)

    def test_drop_reorders_operations_and_rerenders(self) -> None:
        self.page.add_empty_group()
        for index in (1, 1, 1):
            self.page._add_operation_from_menu(index)
        group = self.page.groups[0]
        for offset, operation in enumerate(group.operations):
            operation.key_name = f"K{offset}"
        last_id = group.operations[-1].operation_id

        self.page._on_operation_dropped(last_id, 0)

        self.assertEqual([operation.key_name for operation in group.operations], ["K2", "K0", "K1"])
        first_item = self.page.operation_list.item(0)
        first_editor = self.page.operation_list.itemWidget(first_item)
        self.assertEqual(first_editor.index_label.text(), "动作 1")

    def test_rename_and_enable_are_saved(self) -> None:
        self.page.add_empty_group()
        self.page.group_name_edit.setText("日常连招")
        self.page._save_group_name()
        self.page._set_group_enabled(True)

        reloaded = ComboStore(self.store_path).load()
        self.assertEqual(reloaded[0].name, "日常连招")
        self.assertTrue(reloaded[0].enabled)

    def test_delete_removes_group_when_confirmed(self) -> None:
        self.page.add_empty_group()
        self.page.add_empty_group()
        group_id = self.page.groups[0].group_id

        from unittest.mock import MagicMock, patch

        class _FakeDialog:
            DialogCode = type("DialogCode", (), {"Accepted": 1})

            def __init__(self, *args, **kwargs) -> None:
                self.yesButton = MagicMock()
                self.cancelButton = MagicMock()

            def exec(self) -> int:
                return 1

        with patch("better_clx.ui.combo_page.MessageBox", return_value=_FakeDialog()):
            self.page._confirm_delete_group(group_id)

        self.assertEqual(len(self.page.groups), 1)
        self.assertNotIn(group_id, [group.group_id for group in self.page.groups])

    def test_delete_keeps_group_when_cancelled(self) -> None:
        self.page.add_empty_group()
        group_id = self.page.groups[0].group_id

        from unittest.mock import MagicMock, patch

        class _FakeDialog:
            DialogCode = type("DialogCode", (), {"Accepted": 1})

            def __init__(self, *args, **kwargs) -> None:
                self.yesButton = MagicMock()
                self.cancelButton = MagicMock()

            def exec(self) -> int:
                return 0

        with patch("better_clx.ui.combo_page.MessageBox", return_value=_FakeDialog()):
            self.page._confirm_delete_group(group_id)

        self.assertEqual(len(self.page.groups), 1)

    def test_export_and_import_round_trip_through_dialogs(self) -> None:
        self.page.add_empty_group()
        self.page._add_operation_from_menu(1)
        self.page.groups[0].name = "分享组"
        exported = Path(self._temp_dir.name) / "shared.combo.json"

        from unittest.mock import patch

        with patch(
            "better_clx.ui.combo_page.QFileDialog.getSaveFileName",
            return_value=(str(exported), "combo"),
        ):
            self.page.export_active_group()
        self.assertTrue(exported.is_file())

        with patch(
            "better_clx.ui.combo_page.QFileDialog.getOpenFileName",
            return_value=(str(exported), "combo"),
        ):
            self.page.import_group()

        self.assertEqual(len(self.page.groups), 2)
        self.assertEqual(self.page.groups[1].name, "分享组")
        self.assertNotEqual(self.page.groups[0].group_id, self.page.groups[1].group_id)

    def test_delay_input_converts_seconds_to_milliseconds(self) -> None:
        self.page.add_empty_group()
        self.page._add_operation_from_menu(2)
        item = self.page.operation_list.item(0)
        editor = self.page.operation_list.itemWidget(item)
        editor.delay_unit.setCurrentText("s")
        editor.delay_spin.setValue(1.5)
        self.assertEqual(editor.operation.delay_ms, 1500)
        editor.delay_unit.setCurrentText("ms")
        self.assertEqual(round(editor.delay_spin.value()), 1500)

    def test_target_label_follows_binding(self) -> None:
        self.assertIn("未绑定窗口", self.page.target_label.text())
        self.controller._bound_hwnd = 0xABCD
        self.controller.bound_changed.emit(0xABCD)
        self.assertIn("0xABCD", self.page.target_label.text())

    def test_mouse_capture_stops_listening_after_external_click(self) -> None:
        button = KeyListenButton(continuous=False)
        captured: list[str] = []
        button.mouse_captured.connect(captured.append)
        button._start_listening()
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        other_widget = QWidget()
        self.assertTrue(button.eventFilter(other_widget, event))
        self.assertEqual(captured, ["鼠标左键"])
        self.assertFalse(button.listening)
        button.deleteLater()
        other_widget.deleteLater()


if __name__ == "__main__":
    unittest.main()