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
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 7, 8, 7)
        root.setSpacing(5)

        self.name_label = QLabel(group.name or "未命名连招组", self)
        self.name_label.setToolTip(group.name)
        self.name_label.setMinimumHeight(22)
        root.addWidget(self.name_label)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.state_label = QLabel("运行中" if active else ("已启用" if group.enabled else "已停用"), self)
        self.state_label.setStyleSheet(f"color: {'#16803c' if active else MUTED}; font-size: 11px;")
        controls.addWidget(self.state_label, 1)

        self.enabled_switch = SwitchButton("", self)
        self.enabled_switch.setOnText("")
        self.enabled_switch.setOffText("")
        self.enabled_switch.setMinimumWidth(58)
        self.enabled_switch.setFixedHeight(24)
        self.enabled_switch.setToolTip("启用/停用连招组")
        self.enabled_switch.setChecked(group.enabled)
        self.enabled_switch.checkedChanged.connect(lambda value: self.enabled_changed.emit(group.group_id, value))
        controls.addWidget(self.enabled_switch, 0, Qt.AlignmentFlag.AlignVCenter)

        self.export_button = PushButton("分享", self)
        self.export_button.setToolTip("导出连招组")
        self.export_button.setFixedSize(54, 32)
        self.export_button.setStyleSheet("QPushButton { padding: 0 4px; }")
        self.export_button.clicked.connect(lambda: self.export_requested.emit(group.group_id))
        controls.addWidget(self.export_button)

        self.delete_button = PushButton("删除", self)
        self.delete_button.setToolTip("删除连招组")
        self.delete_button.setFixedSize(54, 32)
        self.delete_button.setStyleSheet(
            "QPushButton { color: #b42318; padding: 0 4px; } "
            "QPushButton:hover { color: #8f1d14; background: #fee4e2; }"
        )
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(group.group_id))
        controls.addWidget(self.delete_button)
        root.addLayout(controls)
        self.set_active(active)

    def set_active(self, active: bool) -> None:
        self.active = active
        self.state_label.setText("运行中" if active else ("已启用" if self.group.enabled else "已停用"))
        self.state_label.setStyleSheet(f"color: {'#16803c' if active else MUTED}; font-size: 11px;")

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
