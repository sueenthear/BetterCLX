"""Left-side combo group list and group actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import PushButton, SwitchButton

from better_clx.combo_models import ComboGroup
from better_clx.ui.theme import MUTED


class ComboGroupRow(QWidget):
    selected = Signal(str)
    enabled_changed = Signal(str, bool)
    delete_requested = Signal(str)
    export_requested = Signal(str)

    def __init__(self, group: ComboGroup, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.group = group
        self.active = active
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 5, 8, 5)
        root.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        self.status_dot = QLabel("●", self)
        self.status_dot.setFixedWidth(14)
        title_row.addWidget(self.status_dot)
        self.name_label = QLabel(group.name or "未命名连招组", self)
        self.name_label.setToolTip(group.name)
        self.name_label.setMinimumHeight(22)
        title_row.addWidget(self.name_label, 1)
        self.state_label = QLabel(self)
        title_row.addWidget(self.state_label)
        root.addLayout(title_row)

        self.controls = QWidget(self)
        controls = QHBoxLayout(self.controls)
        controls.setContentsMargins(20, 0, 0, 0)
        controls.setSpacing(5)
        self.enabled_switch = SwitchButton("", self.controls)
        self.enabled_switch.setOnText("")
        self.enabled_switch.setOffText("")
        self.enabled_switch.setMinimumWidth(54)
        self.enabled_switch.setFixedHeight(22)
        self.enabled_switch.setToolTip("启用/停用连招组")
        self.enabled_switch.setChecked(group.enabled)
        self.enabled_switch.checkedChanged.connect(lambda value: self.enabled_changed.emit(group.group_id, value))
        controls.addWidget(self.enabled_switch)
        self.export_button = PushButton("分享", self.controls)
        self.export_button.setFixedSize(52, 28)
        self.export_button.clicked.connect(lambda: self.export_requested.emit(group.group_id))
        controls.addWidget(self.export_button)
        self.delete_button = PushButton("删除", self.controls)
        self.delete_button.setFixedSize(52, 28)
        self.delete_button.setStyleSheet("QPushButton { color: #b42318; }")
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(group.group_id))
        controls.addWidget(self.delete_button)
        controls.addStretch(1)
        root.addWidget(self.controls)
        self.set_active(active)
        self.set_focused(False)

    def set_active(self, active: bool) -> None:
        self.active = active
        if active and self.group.enabled:
            state_text, color = "运行中", "#16803c"
        elif self.group.enabled:
            state_text, color = "已启用", "#1677ff"
        else:
            state_text, color = "已停用", "#b42318"
        self.state_label.setText(state_text)
        self.state_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 13px;")

    def set_focused(self, focused: bool) -> None:
        self.controls.setVisible(focused)
        self.setMinimumHeight(74 if focused else 42)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.group.group_id)


def create_group_item(group: ComboGroup, active: bool, parent: QWidget) -> tuple[QListWidgetItem, ComboGroupRow]:
    item = QListWidgetItem()
    item.setData(Qt.ItemDataRole.UserRole, group.group_id)
    row = ComboGroupRow(group, active, parent)
    item.setSizeHint(row.sizeHint())
    return item, row
