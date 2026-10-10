"""连招动作块编辑器与键盘监听控件。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, FluentIcon, LineEdit, PushButton, StrongBodyLabel

from better_clx.combo_models import ComboOperation, KeyboardAction, OperationType, ScrollDirection
from better_clx.services.win32_input import qt_key_name
from better_clx.ui.theme import MUTED

OPERATION_MIME = "application/x-clx-combo-operation"


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """Delay input must not change when the editor is scrolled."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class DragHandle(QLabel):
    def __init__(self, operation_id: str, parent: QWidget | None = None) -> None:
        super().__init__("⋮⋮", parent)
        self.operation_id = operation_id
        self.setToolTip("按住拖动调整动作顺序")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedWidth(18)
        self._press_position: QPoint | None = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._press_position is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self._press_position).manhattanLength() < 8:
            return
        mime = QMimeData()
        mime.setData(OPERATION_MIME, self.operation_id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        self._press_position = None
        drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._press_position = None
        super().mouseReleaseEvent(event)


class KeyListenButton(PushButton):
    key_captured = Signal(str)
    mouse_captured = Signal(str)

    def __init__(self, continuous: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText("监听获取")
        self.continuous = continuous
        self.listening = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus
        )

    def _start_listening(self) -> None:
        self.listening = True
        self.setText("监听中")
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.listening:
            button_names = {
                Qt.MouseButton.LeftButton: "鼠标左键",
                Qt.MouseButton.RightButton: "鼠标右键",
                Qt.MouseButton.MiddleButton: "鼠标中键",
            }
            name = button_names.get(event.button())
            if name:
                self.mouse_captured.emit(name)
                self.stop_listening()
                event.accept()
                return
        self._start_listening()
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self.listening:
            self.mouse_captured.emit("滚轮上" if event.angleDelta().y() > 0 else "滚轮下")
            self.stop_listening()
            event.accept()
            return
        super().wheelEvent(event)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if self.listening and watched is not self:
            if event.type() == QEvent.Type.MouseButtonPress:
                button_names = {
                    Qt.MouseButton.LeftButton: "鼠标左键",
                    Qt.MouseButton.RightButton: "鼠标右键",
                    Qt.MouseButton.MiddleButton: "鼠标中键",
                }
                name = button_names.get(event.button())
                if name:
                    self.mouse_captured.emit(name)
                    self.stop_listening()
                    return True
            elif event.type() == QEvent.Type.Wheel:
                self.mouse_captured.emit("滚轮上" if event.angleDelta().y() > 0 else "滚轮下")
                self.stop_listening()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self.listening:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.stop_listening()
        else:
            name = qt_key_name(event.key(), event.text())
            if name:
                self.key_captured.emit(name)
                if not self.continuous:
                    self.stop_listening()
        event.accept()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        if self.listening and not self.continuous:
            self.stop_listening()
        super().focusOutEvent(event)

    def stop_listening(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.listening = False
        self.setText("监听获取")


class OperationEditor(QWidget):
    changed = Signal()
    remove_requested = Signal(str)

    def __init__(self, operation: ComboOperation, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.operation = operation
        self.index = index
        self.setObjectName("operationEditor")
        self.setMinimumHeight(118)
        self.setStyleSheet(
            "QWidget#operationEditor { border: 1px solid rgba(128,128,128,45); "
            "border-radius: 8px; background: rgba(255,255,255,25); }"
        )
        self._build_ui()
        self._rebuild_detail()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(7)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.drag_handle = DragHandle(self.operation.operation_id, self)
        self.drag_handle.setStyleSheet(f"color: {MUTED}; font-size: 16px;")
        header.addWidget(self.drag_handle)
        self.index_label = StrongBodyLabel(f"动作 {self.index}", self)
        header.addWidget(self.index_label)
        self.type_combo = ComboBox(self)
        self.type_combo.addItems([item.label for item in OperationType])
        self.type_combo.setCurrentIndex(list(OperationType).index(OperationType(self.operation.operation_type)))
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        header.addWidget(self.type_combo)
        header.addStretch(1)
        self.remove_button = PushButton("删除", self)
        self.remove_button.setFixedSize(72, 32)
        self.remove_button.setStyleSheet("QPushButton { color: #b42318; }")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.operation.operation_id))
        header.addWidget(self.remove_button)
        root.addLayout(header)
        self.detail_host = QWidget(self)
        self.detail_layout = QHBoxLayout(self.detail_host)
        self.detail_layout.setContentsMargins(26, 0, 0, 0)
        self.detail_layout.setSpacing(8)
        root.addWidget(self.detail_host)

    def _clear_detail(self) -> None:
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _rebuild_detail(self) -> None:
        self._clear_detail()
        kind = OperationType(self.operation.operation_type)
        if kind is OperationType.KEYBOARD:
            self.detail_layout.addWidget(BodyLabel("按键", self.detail_host))
            self.key_edit = LineEdit(self.detail_host)
            self.key_edit.setReadOnly(True)
            self.key_edit.setPlaceholderText("监听获取")
            self.key_edit.setText(self.operation.key_name)
            self.detail_layout.addWidget(self.key_edit, 1)
            listen = KeyListenButton(False, self.detail_host)
            listen.key_captured.connect(self._set_key_name)
            listen.mouse_captured.connect(self._set_key_name)
            self.detail_layout.addWidget(listen)
            self.detail_layout.addWidget(BodyLabel("动作", self.detail_host))
            action = ComboBox(self.detail_host)
            action.addItems(["按下", "抬起"])
            action.setCurrentIndex(0 if self.operation.keyboard_action == KeyboardAction.PRESS.value else 1)
            action.currentIndexChanged.connect(self._set_keyboard_action)
            self.detail_layout.addWidget(action)
        elif kind is OperationType.DELAY:
            self.detail_layout.addWidget(BodyLabel("等待时长", self.detail_host))
            self.delay_spin = NoWheelDoubleSpinBox(self.detail_host)
            self.delay_spin.setRange(0.0, 3_600.0)
            self.delay_spin.setDecimals(2)
            self.delay_spin.setSingleStep(0.1)
            self.delay_spin.setFixedHeight(32)
            self.delay_spin.setValue(self.operation.delay_value)
            self.delay_spin.valueChanged.connect(self._set_delay_value)
            self.detail_layout.addWidget(self.delay_spin)
            self.delay_unit = QComboBox(self.detail_host)
            self.delay_unit.addItems(["s", "ms"])
            self.delay_unit.setFixedWidth(72)
            self.delay_unit.setFixedHeight(32)
            self.delay_unit.setCurrentText(self.operation.delay_unit)
            self.delay_unit.currentTextChanged.connect(self._set_delay_unit)
            self.detail_layout.addWidget(self.delay_unit)
            self.detail_layout.addStretch(1)
        else:
            self.detail_layout.addWidget(BodyLabel("滚轮", self.detail_host))
            scroll = ComboBox(self.detail_host)
            scroll.addItems(["中键上滚", "中键下滚"])
            scroll.setCurrentIndex(0 if self.operation.scroll_direction == ScrollDirection.UP.value else 1)
            scroll.currentIndexChanged.connect(self._set_scroll)
            self.detail_layout.addWidget(scroll)
            self.detail_layout.addStretch(1)

    def _on_type_changed(self, index: int) -> None:
        self.operation.operation_type = list(OperationType)[index].value
        self._rebuild_detail()
        self.changed.emit()

    def _set_key_name(self, name: str) -> None:
        self.operation.key_name = name
        self.key_edit.setText(name)
        self.changed.emit()

    def _set_keyboard_action(self, index: int) -> None:
        self.operation.keyboard_action = KeyboardAction.PRESS.value if index == 0 else KeyboardAction.RELEASE.value
        self.changed.emit()

    def _set_delay_value(self, value: float) -> None:
        unit = self.delay_unit.currentText()
        self.operation.delay_value = max(0.0, float(value))
        self.operation.delay_unit = unit
        self.operation.delay_ms = round(self.operation.delay_value * 1000 if unit == "s" else self.operation.delay_value)
        self.changed.emit()

    def _set_delay_unit(self, unit: str) -> None:
        self.operation.delay_unit = unit
        self.operation.delay_value = self.operation.delay_ms / 1000.0 if unit == "s" else float(self.operation.delay_ms)
        self.delay_spin.blockSignals(True)
        self.delay_spin.setValue(self.operation.delay_value)
        self.delay_spin.blockSignals(False)
        self.changed.emit()

    def _set_scroll(self, index: int) -> None:
        self.operation.scroll_direction = ScrollDirection.UP.value if index == 0 else ScrollDirection.DOWN.value
        self.changed.emit()

    def set_index(self, index: int) -> None:
        self.index = index
        self.index_label.setText(f"动作 {index}")
