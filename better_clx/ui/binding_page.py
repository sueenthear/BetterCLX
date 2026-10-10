"""窗口检测、单击聚焦和单窗口绑定页面。"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from better_clx.models import GameWindow, WindowStatus
from better_clx.services.window_actions import WindowBindingController
from better_clx.ui.theme import CONTENT_MARGIN, MUTED, SUCCESS, WARNING


class BindingPage(QWidget):
    """List detected game windows and manage one bound HWND."""

    refresh_requested = Signal()
    FOCUS_DELAY_MS = 450
    _COL_STATUS = 0
    _COL_BOUND = 1
    _COL_HWND = 2
    _COL_PID = 3
    _COL_TITLE = 4
    _COL_SIZE = 5
    _COL_LOGIN = 6
    _HEADERS = ("状态", "绑定", "HWND", "PID", "窗口标题", "客户区", "登录窗口")

    def __init__(
        self,
        controller: WindowBindingController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bindingPage")
        self.controller = controller
        self._windows: list[GameWindow] = []
        self._pending_hwnd: int | None = None
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.setInterval(self.FOCUS_DELAY_MS)
        self._focus_timer.timeout.connect(self._focus_pending_window)
        self.controller.bound_changed.connect(self._on_bound_changed)
        self.controller.fullscreen_changed.connect(self._on_fullscreen_changed)
        self.controller.action_failed.connect(self._show_error)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*CONTENT_MARGIN)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(SubtitleLabel("绑定", self))
        subtitle = BodyLabel("查看游戏窗口并绑定唯一目标窗口", self)
        subtitle.setStyleSheet(f"color: {MUTED};")
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch(1)
        self.refresh_button = PushButton(FluentIcon.SYNC, "立即刷新", self)
        self.refresh_button.clicked.connect(self.refresh_requested)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        target_card = CardWidget(self)
        target_layout = QHBoxLayout(target_card)
        target_layout.setContentsMargins(18, 12, 18, 12)
        target_layout.setSpacing(14)
        target_layout.addWidget(StrongBodyLabel("当前绑定", target_card))
        self.bound_label = BodyLabel("未绑定窗口", target_card)
        self.bound_label.setStyleSheet(f"color: {MUTED};")
        target_layout.addWidget(self.bound_label, 1)
        self.unbind_button = PushButton(FluentIcon.LINK, "解绑窗口", target_card)
        self.unbind_button.clicked.connect(self._unbind)
        target_layout.addWidget(self.unbind_button)
        self.fullscreen_button = PrimaryPushButton(FluentIcon.FULL_SCREEN, "全屏窗口 · F11", target_card)
        self.fullscreen_button.clicked.connect(self.controller.toggle_fullscreen)
        target_layout.addWidget(self.fullscreen_button)
        root.addWidget(target_card)

        table_card = CardWidget(self)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(8)
        table_hint = CaptionLabel("单击聚焦窗口，双击绑定窗口", table_card)
        table_hint.setStyleSheet(f"color: {MUTED};")
        table_layout.addWidget(table_hint)
        self.table = QTableWidget(table_card)
        self.table.setColumnCount(len(self._HEADERS))
        self.table.setHorizontalHeaderLabels(list(self._HEADERS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(280)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self._COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_BOUND, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_HWND, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_PID, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self._COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_LOGIN, QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellClicked.connect(self._on_clicked)
        self.table.cellDoubleClicked.connect(self._on_double_clicked)
        table_layout.addWidget(self.table)
        root.addWidget(table_card, 1)

        self.last_scan = CaptionLabel("等待首次扫描", self)
        self.last_scan.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self.last_scan)
        self._refresh_actions()

    def set_windows(self, windows: Sequence[GameWindow]) -> None:
        self._windows = list(windows)
        if self.controller.bound_hwnd is not None and not any(
            window.hwnd == self.controller.bound_hwnd for window in self._windows
        ):
            self.controller.unbind()
        self._render_windows()

    def set_scan_time(self, text: str) -> None:
        self.last_scan.setText(text)

    def _render_windows(self) -> None:
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        bound_hwnd = self.controller.bound_hwnd
        for row, window in enumerate(self._windows):
            self.table.insertRow(row)
            values = (
                window.status.value,
                "已绑定" if window.hwnd == bound_hwnd else "",
                f"0x{window.hwnd:X}",
                str(window.pid),
                window.title,
                f"{window.client_width} × {window.client_height}",
                f"0x{window.login_hwnd:X}" if window.login_hwnd else "",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, window.hwnd)
                self.table.setItem(row, column, item)
            status_item = self.table.item(row, self._COL_STATUS)
            if status_item is not None:
                color = WARNING if window.status is WindowStatus.LOGGING_IN else SUCCESS
                status_item.setForeground(QColor(color))
            if window.hwnd == bound_hwnd:
                for column in range(self.table.columnCount()):
                    item = self.table.item(row, column)
                    if item is not None:
                        item.setBackground(QColor(0, 120, 215, 55))
        self.table.setUpdatesEnabled(True)
        self._refresh_actions()

    def _window_for_row(self, row: int) -> GameWindow | None:
        if 0 <= row < len(self._windows):
            return self._windows[row]
        return None

    def _on_clicked(self, row: int, _column: int) -> None:
        window = self._window_for_row(row)
        if window is None:
            return
        self._focus_timer.stop()
        self._pending_hwnd = window.hwnd
        self._focus_timer.start()

    def _on_double_clicked(self, row: int, _column: int) -> None:
        # Cancel the pending single-click action before binding the double-click target.
        self._focus_timer.stop()
        self._pending_hwnd = None
        window = self._window_for_row(row)
        if window is None:
            return
        if self.controller.bind_window(window.hwnd):
            self._show_success(f"已绑定窗口 HWND=0x{window.hwnd:X}")
            self._render_windows()

    def _focus_pending_window(self) -> None:
        hwnd = self._pending_hwnd
        self._pending_hwnd = None
        if hwnd is not None:
            self.controller.focus_window(hwnd)

    def _unbind(self) -> None:
        self.controller.unbind()
        self._show_success("已解绑窗口")
        self._render_windows()

    def _on_bound_changed(self, _hwnd: object) -> None:
        self._render_windows()

    def _on_fullscreen_changed(self, fullscreen: bool) -> None:
        self.fullscreen_button.setText("窗口化 · F11" if fullscreen else "全屏窗口 · F11")
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        bound = self.controller.bound_hwnd is not None
        self.unbind_button.setEnabled(bound)
        self.fullscreen_button.setEnabled(bound)
        if bound:
            self.bound_label.setText(f"HWND 0x{self.controller.bound_hwnd:X}")
            self.bound_label.setStyleSheet(f"color: {SUCCESS}; font-weight: 600;")
        else:
            self.bound_label.setText("未绑定窗口")
            self.bound_label.setStyleSheet(f"color: {MUTED};")

    def _show_success(self, message: str) -> None:
        InfoBar.success(
            title="绑定状态",
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1800,
            parent=self.window(),
        )

    def _show_error(self, message: str) -> None:
        InfoBar.error(
            title="窗口操作失败",
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self.window(),
        )
