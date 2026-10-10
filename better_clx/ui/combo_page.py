"""Two-column combo group manager and ordered operation editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
)

from better_clx.combo_models import ComboGroup, ComboOperation, ComboTrigger, OperationType, TriggerMode
from better_clx.combo_store import ComboStore
from better_clx.services.combo_runtime import ComboRuntime
from better_clx.services.window_actions import WindowBindingController
from better_clx.ui.combo_editor import OPERATION_MIME, KeyListenButton, OperationEditor
from better_clx.ui.combo_group_list import ComboGroupRow
from better_clx.ui.theme import CONTENT_MARGIN, MUTED, SUCCESS


class _OperationList(QListWidget):
    """Order list driven by explicit drag handles and data-model reordering."""

    drop_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("comboOperationList")
        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(8)
        self.setAlternatingRowColors(False)
        self.setStyleSheet("QListWidget { border: none; background: transparent; }")

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.mimeData().hasFormat(OPERATION_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.mimeData().hasFormat(OPERATION_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if not event.mimeData().hasFormat(OPERATION_MIME):
            event.ignore()
            return
        source_id = bytes(event.mimeData().data(OPERATION_MIME)).decode("utf-8")
        position = event.position().toPoint()
        target_row = self.indexAt(position).row()
        if target_row < 0:
            target_row = self.count() - 1
        self.drop_requested.emit(source_id, target_row)
        event.acceptProposedAction()


class ComboPage(QWidget):
    """Manage combo groups and scope runtime output to the bound HWND."""

    def __init__(
        self,
        controller: WindowBindingController,
        parent: QWidget | None = None,
        store: ComboStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("comboPage")
        self.controller = controller
        self.store = store or ComboStore()
        self.groups = self.store.load()
        self.active_group_id: str | None = self.groups[0].group_id if self.groups else None
        self.runtime = ComboRuntime(controller, self)
        self.runtime.set_groups(self.groups)
        self.runtime.group_running_changed.connect(self._on_group_running_changed)
        self._listening_count = 0
        self._runtime_enabled_before_listening = True
        self.runtime.start()
        self._group_rows: dict[str, ComboGroupRow] = {}
        self._operation_editors: dict[str, OperationEditor] = {}
        self._build_ui()
        self._render_groups()
        self._render_editor()
        self.controller.bound_changed.connect(self._on_bound_changed)
        self._refresh_target()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*CONTENT_MARGIN)
        root.setSpacing(14)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(SubtitleLabel("连招", self))
        self.target_label = CaptionLabel(self)
        self.target_label.setStyleSheet(f"color: {MUTED};")
        heading.addWidget(self.target_label)
        header.addLayout(heading)
        header.addStretch(1)
        root.addLayout(header)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        root.addLayout(columns, 1)

        self.group_panel = CardWidget(self)
        self.group_panel.setFixedWidth(310)
        group_root = QVBoxLayout(self.group_panel)
        group_root.setContentsMargins(12, 12, 12, 12)
        group_root.setSpacing(10)
        group_heading = QHBoxLayout()
        group_heading.addWidget(StrongBodyLabel("连招组", self.group_panel))
        group_heading.addStretch(1)
        group_heading.addWidget(BodyLabel("总开关", self.group_panel))
        self.runtime_enabled_switch = SwitchButton("", self.group_panel)
        self.runtime_enabled_switch.setOnText("")
        self.runtime_enabled_switch.setOffText("")
        self.runtime_enabled_switch.setMinimumWidth(58)
        self.runtime_enabled_switch.setFixedHeight(24)
        self.runtime_enabled_switch.setToolTip("监听按键时会临时关闭，监听结束后恢复")
        self.runtime_enabled_switch.setChecked(True)
        self.runtime_enabled_switch.checkedChanged.connect(self._set_runtime_enabled)
        group_heading.addWidget(self.runtime_enabled_switch)
        self.group_count = CaptionLabel("0", self.group_panel)
        group_heading.addWidget(self.group_count)
        group_root.addLayout(group_heading)

        self.group_list = QListWidget(self.group_panel)
        self.group_list.setObjectName("comboGroupList")
        self.group_list.setSpacing(6)
        self.group_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.group_list.setStyleSheet("QListWidget { border: none; background: transparent; }")
        group_root.addWidget(self.group_list, 1)

        create_row = QHBoxLayout()
        self.new_group_button = PushButton("新建空白", self.group_panel)
        self.new_group_button.setMinimumHeight(34)
        self.new_group_button.clicked.connect(self.add_empty_group)
        create_row.addWidget(self.new_group_button, 1)
        self.import_button = PushButton("导入", self.group_panel)
        self.import_button.setMinimumHeight(34)
        self.import_button.clicked.connect(self.import_group)
        create_row.addWidget(self.import_button, 1)
        group_root.addLayout(create_row)
        columns.addWidget(self.group_panel)

        self.editor_panel = CardWidget(self)
        editor_root = QVBoxLayout(self.editor_panel)
        editor_root.setContentsMargins(18, 16, 18, 16)
        editor_root.setSpacing(12)
        columns.addWidget(self.editor_panel, 1)

        self.editor_header = QWidget(self.editor_panel)
        editor_header_layout = QVBoxLayout(self.editor_header)
        editor_header_layout.setContentsMargins(0, 0, 0, 0)
        editor_header_layout.setSpacing(10)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(BodyLabel("组名称", self.editor_header))
        self.group_name_edit = LineEdit(self.editor_header)
        self.group_name_edit.setPlaceholderText("输入连招组名称")
        self.group_name_edit.setMinimumHeight(34)
        self.group_name_edit.editingFinished.connect(self._save_group_name)
        title_row.addWidget(self.group_name_edit, 1)
        title_row.addWidget(BodyLabel("激活", self.editor_header))
        self.group_enabled_switch = SwitchButton("", self.editor_header)
        self.group_enabled_switch.setOnText("")
        self.group_enabled_switch.setOffText("")
        self.group_enabled_switch.setMinimumWidth(58)
        self.group_enabled_switch.setFixedHeight(24)
        self.group_enabled_switch.checkedChanged.connect(self._set_group_enabled)
        title_row.addWidget(self.group_enabled_switch)
        editor_header_layout.addLayout(title_row)

        group_actions = QHBoxLayout()
        group_actions.setSpacing(8)
        group_actions.addStretch(1)
        self.export_group_button = PushButton("分享导出", self.editor_header)
        self.export_group_button.setMinimumSize(104, 34)
        self.export_group_button.clicked.connect(self.export_active_group)
        group_actions.addWidget(self.export_group_button)
        self.delete_group_button = PushButton("删除组", self.editor_header)
        self.delete_group_button.setMinimumSize(88, 34)
        self.delete_group_button.setStyleSheet(
            "QPushButton { color: #b42318; } QPushButton:hover { color: #8f1d14; background: #fee4e2; }"
        )
        self.delete_group_button.clicked.connect(self.confirm_delete_active_group)
        group_actions.addWidget(self.delete_group_button)
        editor_header_layout.addLayout(group_actions)

        trigger_card = CardWidget(self.editor_header)
        trigger_layout = QVBoxLayout(trigger_card)
        trigger_layout.setContentsMargins(12, 10, 12, 10)
        trigger_layout.setSpacing(8)
        trigger_title = QHBoxLayout()
        trigger_title.addWidget(StrongBodyLabel("触发配置", trigger_card))
        trigger_title.addWidget(CaptionLabel("同一组可配置多个触发器，每个触发器独立选择按住或切换", trigger_card))
        trigger_title.addStretch(1)
        self.add_trigger_button = PushButton("添加触发器", trigger_card)
        self.add_trigger_button.setMinimumSize(106, 32)
        self.add_trigger_button.clicked.connect(lambda _checked=False: self._add_group_trigger())
        trigger_title.addWidget(self.add_trigger_button)
        trigger_layout.addLayout(trigger_title)
        self.trigger_rows_host = QWidget(trigger_card)
        self.trigger_rows_layout = QVBoxLayout(self.trigger_rows_host)
        self.trigger_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.trigger_rows_layout.setSpacing(6)
        trigger_layout.addWidget(self.trigger_rows_host)
        editor_header_layout.addWidget(trigger_card)

        actions = QHBoxLayout()
        actions.addWidget(StrongBodyLabel("动作列表", self.editor_header))
        actions.addWidget(CaptionLabel("触发后严格按从上到下顺序执行", self.editor_header))
        actions.addStretch(1)
        self.add_operation_combo = ComboBox(self.editor_header)
        self.add_operation_combo.addItems(["添加操作…", "键盘事件", "延时事件", "鼠标事件"])
        self.add_operation_combo.setCurrentIndex(0)
        self.add_operation_combo.activated.connect(self._add_operation_from_menu)
        actions.addWidget(self.add_operation_combo)
        editor_header_layout.addLayout(actions)
        editor_root.addWidget(self.editor_header)

        self.operation_list = _OperationList(self.editor_panel)
        self.operation_list.drop_requested.connect(self._on_operation_dropped)
        editor_root.addWidget(self.operation_list, 1)

        self.empty_editor = QWidget(self.editor_panel)
        empty_layout = QVBoxLayout(self.empty_editor)
        empty_layout.setContentsMargins(20, 40, 20, 40)
        empty_title = StrongBodyLabel("选择或新建一个连招组", self.empty_editor)
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_hint = CaptionLabel("组数据会自动保存在 combo_groups.json", self.empty_editor)
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setStyleSheet(f"color: {MUTED};")
        empty_layout.addWidget(empty_hint)
        editor_root.addWidget(self.empty_editor, 1)

        self.status_label = CaptionLabel("连招运行器等待绑定窗口", self)
        self.status_label.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self.status_label)
        self.runtime.status_changed.connect(self.status_label.setText)

    def _active_group(self) -> ComboGroup | None:
        return next((group for group in self.groups if group.group_id == self.active_group_id), None)

    def _render_groups(self) -> None:
        self.group_list.clear()
        self._group_rows.clear()
        for group in self.groups:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, group.group_id)
            # Focused selection is separate from the runtime "running" state.
            row = ComboGroupRow(group, False, self.group_list)
            item.setSizeHint(QSize(0, max(row.sizeHint().height(), row.minimumHeight())))
            self.group_list.addItem(item)
            row.selected.connect(self.select_group)
            row.enabled_changed.connect(self._on_group_enabled_changed)
            row.delete_requested.connect(self._confirm_delete_group)
            row.export_requested.connect(self._export_group_id)
            row.name_label.installEventFilter(self)
            row.state_label.installEventFilter(self)
            row.export_button.clicked.connect(lambda _checked=False, group_id=group.group_id: self.select_group(group_id))
            row.delete_button.clicked.connect(lambda _checked=False, group_id=group.group_id: self.select_group(group_id))
            self.group_list.setItemWidget(item, row)
            item.setSizeHint(QSize(0, row.minimumHeight()))
            self._group_rows[group.group_id] = row
        self.group_count.setText(str(len(self.groups)))
        if self.active_group_id and self.active_group_id not in {group.group_id for group in self.groups}:
            self.active_group_id = self.groups[0].group_id if self.groups else None
        self._highlight_selected_group()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API name
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            for group_id, row in self._group_rows.items():
                if obj in (row.name_label, row.state_label):
                    self.select_group(group_id)
                    break
        return super().eventFilter(obj, event)

    def _highlight_selected_group(self) -> None:
        for index in range(self.group_list.count()):
            item = self.group_list.item(index)
            group_id = item.data(Qt.ItemDataRole.UserRole)
            row = self._group_rows.get(group_id)
            if row is None:
                continue
            focused = group_id == self.active_group_id
            row.set_focused(focused)
            item.setSizeHint(QSize(0, row.minimumHeight()))
            row.setStyleSheet(
                "QWidget { border-radius: 6px; background: rgba(0, 120, 215, 38); }"
                if focused
                else "QWidget { border-radius: 6px; background: transparent; }"
            )

    def select_group(self, group_id: str) -> None:
        if group_id not in {group.group_id for group in self.groups}:
            return
        self.active_group_id = group_id
        self._highlight_selected_group()
        self._render_editor()

    def _render_editor(self) -> None:
        group = self._active_group()
        has_group = group is not None
        self.empty_editor.setVisible(not has_group)
        self.editor_header.setVisible(has_group)
        self.operation_list.setVisible(has_group)
        for widget in (
            self.group_name_edit,
            self.group_enabled_switch,
            self.export_group_button,
            self.delete_group_button,
            self.add_operation_combo,
        ):
            widget.setEnabled(has_group)
        self.operation_list.clear()
        self._operation_editors.clear()
        if group is None:
            return
        self.group_name_edit.setText(group.name)
        self.group_enabled_switch.blockSignals(True)
        self.group_enabled_switch.setChecked(group.enabled)
        self.group_enabled_switch.blockSignals(False)
        self.runtime_enabled_switch.blockSignals(True)
        self.runtime_enabled_switch.setChecked(self.runtime.enabled)
        self.runtime_enabled_switch.blockSignals(False)
        self._render_trigger_rows(group)
        for index, operation in enumerate(group.operations, start=1):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, operation.operation_id)
            editor = OperationEditor(operation, index, self.operation_list)
            editor.changed.connect(self._save_active_group)
            editor.remove_requested.connect(self.remove_operation)
            editor.listening_changed.connect(self._on_listening_changed)
            # Item height must respect the editor's minimum height, otherwise the
            # embedded card is taller than its row and neighbouring rows overlap.
            item.setSizeHint(QSize(0, max(editor.sizeHint().height(), editor.minimumHeight())))
            self.operation_list.addItem(item)
            self.operation_list.setItemWidget(item, editor)
            self._operation_editors[operation.operation_id] = editor

    def add_empty_group(self) -> None:
        group = ComboGroup(name=f"连招组 {len(self.groups) + 1}")
        self.groups.append(group)
        self.active_group_id = group.group_id
        self._save_all()
        self._render_groups()
        self._render_editor()

    def import_group(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入连招组",
            str(Path.home()),
            "连招组文件 (*.combo.json *.json);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            group = self.store.import_group(Path(path))
        except (OSError, ValueError, TypeError) as exc:
            self._notify(False, f"导入失败: {exc}")
            return
        self.groups.append(group)
        self.active_group_id = group.group_id
        self._save_all()
        self._render_groups()
        self._render_editor()
        self._notify(True, f"已导入 {group.name}")

    def export_active_group(self) -> None:
        group = self._active_group()
        if group is not None:
            self._export_group_id(group.group_id)

    def _export_group_id(self, group_id: str) -> None:
        group = next((item for item in self.groups if item.group_id == group_id), None)
        if group is None:
            return
        default_name = f"{group.name}.combo.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "分享/导出连招组",
            str(Path.home() / default_name),
            "连招组文件 (*.combo.json);;JSON 文件 (*.json)",
        )
        if not path:
            return
        try:
            self.store.export_group(group, Path(path))
        except OSError as exc:
            self._notify(False, f"导出失败: {exc}")
            return
        self._notify(True, f"已导出 {group.name}")

    def confirm_delete_active_group(self) -> None:
        group = self._active_group()
        if group is not None:
            self._confirm_delete_group(group.group_id)

    def _confirm_delete_group(self, group_id: str) -> None:
        group = next((item for item in self.groups if item.group_id == group_id), None)
        if group is None:
            return
        dialog = MessageBox("删除连招组", f"确定删除“{group.name}”及其全部操作吗？此操作不可撤销。", self)
        dialog.yesButton.setText("删除")
        dialog.cancelButton.setText("取消")
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if group.enabled:
            group.enabled = False
        self.groups = [item for item in self.groups if item.group_id != group_id]
        self.active_group_id = self.groups[0].group_id if self.groups else None
        self._save_all()
        self._render_groups()
        self._render_editor()

    def _save_group_name(self) -> None:
        group = self._active_group()
        if group is None:
            return
        group.name = self.group_name_edit.text().strip() or "未命名连招组"
        row = self._group_rows.get(group.group_id)
        if row is not None:
            row.name_label.setText(group.name)
            row.name_label.setToolTip(group.name)
        self._save_all()

    @staticmethod
    def _dispose_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                ComboPage._dispose_layout(item.layout())

    def _clear_trigger_rows(self) -> None:
        self._dispose_layout(self.trigger_rows_layout)

    def _render_trigger_rows(self, group: ComboGroup) -> None:
        self._clear_trigger_rows()
        row_height = 38
        row_spacing = 6
        total_height = max(row_height, len(group.triggers) * row_height + max(0, len(group.triggers) - 1) * row_spacing)
        self.trigger_rows_host.setMinimumHeight(total_height)
        self.trigger_rows_host.setFixedHeight(total_height)
        self.trigger_rows_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.trigger_rows_layout.setSpacing(row_spacing)
        if not group.triggers:
            self.trigger_rows_layout.addWidget(CaptionLabel("暂无触发器，请点击右上角添加", self.trigger_rows_host))
            return
        for trigger in group.triggers:
            row_widget = QWidget(self.trigger_rows_host)
            row_widget.setMinimumHeight(38)
            row_widget.setFixedHeight(38)
            row_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row = QGridLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setHorizontalSpacing(8)
            row.setVerticalSpacing(0)
            key_label = StrongBodyLabel(trigger.key_name or "未设置", row_widget)
            key_label.setMinimumWidth(88)
            key_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(key_label, 0, 0)
            listen = KeyListenButton(False, row_widget)
            listen.setFixedSize(112, 32)
            listen.key_captured.connect(lambda key, trigger_id=trigger.trigger_id: self._set_trigger_key(trigger_id, key))
            listen.mouse_captured.connect(lambda key, trigger_id=trigger.trigger_id: self._set_trigger_key(trigger_id, key))
            listen.listening_changed.connect(self._on_listening_changed)
            row.addWidget(listen, 0, 1)
            mode = ComboBox(row_widget)
            mode.addItems(["按住", "切换"])
            mode.setFixedWidth(86)
            mode.setCurrentIndex(0 if trigger.mode == TriggerMode.HOLD.value else 1)
            mode.currentIndexChanged.connect(lambda index, trigger_id=trigger.trigger_id: self._set_trigger_mode(trigger_id, index))
            row.addWidget(mode, 0, 2)
            delete = PushButton("删除", row_widget)
            delete.setFixedSize(72, 32)
            delete.setStyleSheet("QPushButton { color: #b42318; }")
            delete.clicked.connect(lambda _checked=False, trigger_id=trigger.trigger_id: self._remove_trigger(trigger_id))
            row.addWidget(delete, 0, 3)
            row.setColumnStretch(0, 1)
            self.trigger_rows_layout.addWidget(row_widget)

    def _add_group_trigger(self) -> None:
        group = self._active_group()
        if group is None:
            return
        group.triggers.append(ComboTrigger())
        self._save_all()
        self._render_editor()

    def _set_trigger_key(self, trigger_id: str, key_name: str) -> None:
        group = self._active_group()
        if group is None:
            return
        trigger = next((item for item in group.triggers if item.trigger_id == trigger_id), None)
        if trigger is None:
            return
        trigger.key_name = key_name
        self._save_all()
        self._render_editor()

    def _set_trigger_mode(self, trigger_id: str, index: int) -> None:
        group = self._active_group()
        if group is None:
            return
        trigger = next((item for item in group.triggers if item.trigger_id == trigger_id), None)
        if trigger is None:
            return
        trigger.mode = TriggerMode.HOLD.value if index == 0 else TriggerMode.TOGGLE.value
        self._save_all()
        self._render_editor()

    def _remove_trigger(self, trigger_id: str) -> None:
        group = self._active_group()
        if group is None:
            return
        group.triggers = [item for item in group.triggers if item.trigger_id != trigger_id]
        self._save_all()
        self._render_editor()

    def _set_runtime_enabled(self, enabled: bool) -> None:
        self.runtime.set_enabled(enabled)

    def _on_listening_changed(self, listening: bool) -> None:
        if listening:
            if self._listening_count == 0:
                self._runtime_enabled_before_listening = self.runtime.enabled
                self.runtime.set_enabled(False)
                self.runtime_enabled_switch.blockSignals(True)
                self.runtime_enabled_switch.setChecked(False)
                self.runtime_enabled_switch.blockSignals(False)
            self._listening_count += 1
            return
        self._listening_count = max(0, self._listening_count - 1)
        if self._listening_count == 0:
            restored = self._runtime_enabled_before_listening
            self.runtime.set_enabled(restored)
            self.runtime_enabled_switch.blockSignals(True)
            self.runtime_enabled_switch.setChecked(restored)
            self.runtime_enabled_switch.blockSignals(False)

    def _set_group_enabled(self, enabled: bool) -> None:
        group = self._active_group()
        if group is None:
            return
        group.enabled = enabled
        row = self._group_rows.get(group.group_id)
        if row is not None:
            row.enabled_switch.blockSignals(True)
            row.enabled_switch.setChecked(enabled)
            row.enabled_switch.blockSignals(False)
            row.set_active(row.active if enabled else False)
        self._save_all()

    def _on_group_enabled_changed(self, group_id: str, enabled: bool) -> None:
        group = next((item for item in self.groups if item.group_id == group_id), None)
        if group is None:
            return
        group.enabled = enabled
        if group_id == self.active_group_id:
            self.group_enabled_switch.blockSignals(True)
            self.group_enabled_switch.setChecked(enabled)
            self.group_enabled_switch.blockSignals(False)
        row = self._group_rows.get(group_id)
        if row is not None:
            row.set_active(row.active if enabled else False)
        self._save_all()

    def _add_operation_from_menu(self, index: int) -> None:
        if index == 0:
            return
        operation_types = (None, OperationType.KEYBOARD, OperationType.DELAY, OperationType.MOUSE_SCROLL)
        operation_type = operation_types[index]
        group = self._active_group()
        if group is None or operation_type is None:
            return
        group.operations.append(ComboOperation(operation_type=operation_type.value))
        self.add_operation_combo.setCurrentIndex(0)
        self._save_all()
        self._render_editor()

    def remove_operation(self, operation_id: str) -> None:
        group = self._active_group()
        if group is None:
            return
        group.operations = [operation for operation in group.operations if operation.operation_id != operation_id]
        self._save_all()
        self._render_editor()

    def _on_operation_dropped(self, source_id: str, target_row: int) -> None:
        group = self._active_group()
        if group is None:
            return
        source_index = next(
            (index for index, operation in enumerate(group.operations) if operation.operation_id == source_id),
            None,
        )
        if source_index is None:
            return
        operations = list(group.operations)
        moved = operations.pop(source_index)
        target_row = max(0, min(target_row, len(operations)))
        operations.insert(target_row, moved)
        group.operations = operations
        self._save_all()
        self._render_editor()
        self._notify(True, f"已调整顺序：{moved.key_name or moved.operation_type}")

    def _save_active_group(self) -> None:
        self._save_all()

    def _save_all(self) -> None:
        self.runtime.set_groups(self.groups)
        self.store.save(self.groups)
        self._render_groups()

    def _on_group_running_changed(self, group_id: str, active: bool) -> None:
        row = self._group_rows.get(group_id)
        if row is not None:
            row.set_active(active)

    def _on_bound_changed(self, _hwnd: object) -> None:
        self._refresh_target()

    def _refresh_target(self) -> None:
        hwnd = self.controller.bound_hwnd
        if hwnd:
            self.target_label.setText(f"输出目标 HWND 0x{hwnd:X} · 输入只发送到此窗口")
            self.target_label.setStyleSheet(f"color: {SUCCESS};")
        else:
            self.target_label.setText("未绑定窗口 · 连招触发不会发送输入")
            self.target_label.setStyleSheet(f"color: {MUTED};")

    def _notify(self, success: bool, message: str) -> None:
        method = InfoBar.success if success else InfoBar.error
        method(
            title="操作完成" if success else "操作失败",
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2800 if success else 4500,
            parent=self.window(),
        )

    def shutdown(self) -> None:
        """Stop the runtime and release keys; called when the main window closes."""
        self.runtime.stop()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self.shutdown()
        super().closeEvent(event)
