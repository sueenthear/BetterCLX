"""Launcher cards used by the start page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    ComboBox,
    FluentIcon,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
)

from better_clx.services.launcher import (
    LaunchResult,
    game_status,
    launch_game,
    launch_script,
    open_update_url,
    search_wyclx_folder,
)
from better_clx.services.settings import AppSettings, ScriptConfig, SettingsStore
from better_clx.ui.theme import MUTED, SUCCESS, WARNING


class SearchWorker(QThread):
    """Run disk discovery away from the Qt UI thread."""

    result_ready = Signal(str)

    def __init__(self, timeout: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.timeout = timeout

    def run(self) -> None:
        self.result_ready.emit(search_wyclx_folder(timeout=self.timeout))


def show_result(parent: QWidget, result: LaunchResult) -> None:
    """Show a compact result notification through the host window."""
    from qfluentwidgets import InfoBar, InfoBarPosition

    method = InfoBar.success if result.success else InfoBar.error
    method(
        title="操作完成" if result.success else "操作失败",
        content=result.message,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=2600 if result.success else 4200,
        parent=parent.window(),
    )


class GameLauncherCard(CardWidget):
    """Game path/version configuration and one-click game launch."""

    _VERSION_VALUES = ("64", "32", "auto")
    _VERSION_LABELS = (
        "64 位 · wyclx64.exe",
        "32 位 · wyclx.exe",
        "自动选择 (有更新时建议选择)",
    )

    def __init__(
        self,
        settings: AppSettings,
        store: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.store = store
        self._search_thread: SearchWorker | None = None
        self.setMinimumHeight(190)
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(StrongBodyLabel("快速启动游戏", self))
        header.addStretch(1)
        self.status_label = CaptionLabel(self)
        header.addWidget(self.status_label)
        root.addLayout(header)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.addWidget(CaptionLabel("游戏路径", self))
        self.path_edit = LineEdit(self)
        self.path_edit.setPlaceholderText("填写游戏根目录，或使用右侧 BFS 查找")
        self.path_edit.setText(self.settings.game_path)
        self.path_edit.editingFinished.connect(self._save_path)
        path_row.addWidget(self.path_edit, 1)
        self.choose_path_button = PushButton(FluentIcon.FOLDER, "选择目录", self)
        self.choose_path_button.clicked.connect(self._choose_path)
        path_row.addWidget(self.choose_path_button)
        self.search_button = PushButton(FluentIcon.SEARCH, "BFS 查找", self)
        self.search_button.clicked.connect(self._search_game)
        path_row.addWidget(self.search_button)
        root.addLayout(path_row)

        control_row = QHBoxLayout()
        control_row.setSpacing(8)
        control_row.addWidget(CaptionLabel("启动版本", self))
        self.version_combo = ComboBox(self)
        self.version_combo.addItems(list(self._VERSION_LABELS))
        self.version_combo.setCurrentIndex(self._VERSION_VALUES.index(self.settings.game_version))
        self.version_combo.currentIndexChanged.connect(self._save_version)
        control_row.addWidget(self.version_combo)
        control_row.addStretch(1)
        self.launch_button = PrimaryPushButton(FluentIcon.PLAY, "启动游戏", self)
        self.launch_button.clicked.connect(self.launch)
        control_row.addWidget(self.launch_button)
        root.addLayout(control_row)

    def _save_path(self) -> None:
        self.settings.game_path = self.path_edit.text().strip().strip('"')
        self.store.save(self.settings)
        self.refresh_status()

    def _choose_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择游戏根目录",
            self.settings.game_path or str(Path.home()),
        )
        if path:
            self.path_edit.setText(path)
            self._save_path()

    def _save_version(self, index: int) -> None:
        self.settings.game_version = self._VERSION_VALUES[index]
        self.store.save(self.settings)
        self.refresh_status()

    def refresh_status(self) -> None:
        valid, detail = game_status(self.settings)
        self.status_label.setText(detail)
        self.status_label.setStyleSheet(f"color: {SUCCESS if valid else MUTED};")
        self.launch_button.setEnabled(valid)

    def _search_game(self) -> None:
        if self._search_thread is not None:
            return
        self._search_thread = SearchWorker(self.settings.search_timeout, self)
        self._search_thread.result_ready.connect(self._on_search_result)
        self._search_thread.finished.connect(self._on_search_finished)
        self.search_button.setEnabled(False)
        self.search_button.setText("搜索中...")
        self.status_label.setText(f"正在搜索磁盘（最长 {self.settings.search_timeout} 秒）")
        self.status_label.setStyleSheet(f"color: {WARNING};")
        self._search_thread.start()

    def _on_search_result(self, path: str) -> None:
        if path:
            self.settings.game_path = path
            self.path_edit.setText(path)
            self.store.save(self.settings)
            self.status_label.setText(f"已找到游戏目录: {path}")
        else:
            self.status_label.setText("未找到有效的 wyclx 游戏目录")
        self.refresh_status()

    def _on_search_finished(self) -> None:
        self.search_button.setEnabled(True)
        self.search_button.setText("BFS 查找")
        if self._search_thread is not None:
            self._search_thread.deleteLater()
            self._search_thread = None

    def launch(self, show_notice: bool = True) -> LaunchResult:
        result = launch_game(self.settings)
        if show_notice:
            show_result(self, result)
        return result


class ScriptLauncherCard(CardWidget):
    """One independently editable and launchable script."""

    changed = Signal()
    removed = Signal(str)

    def __init__(
        self,
        script: ScriptConfig,
        settings: AppSettings,
        store: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.script = script
        self.settings = settings
        self.store = store
        self.setMinimumHeight(184)
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(StrongBodyLabel("脚本", self))
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("脚本名称")
        self.name_edit.setText(self.script.name)
        self.name_edit.setMaximumWidth(220)
        self.name_edit.editingFinished.connect(self._save_fields)
        header.addWidget(self.name_edit)
        header.addStretch(1)
        self.status_label = CaptionLabel(self)
        header.addWidget(self.status_label)
        self.delete_button = PushButton(FluentIcon.DELETE, "删除", self)
        self.delete_button.clicked.connect(lambda: self.removed.emit(self.script.script_id))
        header.addWidget(self.delete_button)
        root.addLayout(header)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.addWidget(CaptionLabel("启动路径", self))
        self.path_edit = LineEdit(self)
        self.path_edit.setPlaceholderText(".bat / .cmd / .exe / .py")
        self.path_edit.setText(self.script.path)
        self.path_edit.editingFinished.connect(self._save_fields)
        path_row.addWidget(self.path_edit, 1)
        self.choose_button = PushButton(FluentIcon.FOLDER, "选择", self)
        self.choose_button.clicked.connect(self._choose_script)
        path_row.addWidget(self.choose_button)
        self.launch_button = PrimaryPushButton(FluentIcon.PLAY, "启动", self)
        self.launch_button.clicked.connect(self.launch)
        path_row.addWidget(self.launch_button)
        root.addLayout(path_row)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        url_row.addWidget(CaptionLabel("更新网址", self))
        self.url_edit = LineEdit(self)
        self.url_edit.setPlaceholderText("为此脚本配置独立的更新网址")
        self.url_edit.setText(self.script.update_url)
        self.url_edit.editingFinished.connect(self._save_fields)
        url_row.addWidget(self.url_edit, 1)
        self.open_url_button = PushButton(FluentIcon.GLOBE, "打开更新页", self)
        self.open_url_button.clicked.connect(self.open_update)
        url_row.addWidget(self.open_url_button)
        root.addLayout(url_row)

    def _save_fields(self) -> None:
        self.script.name = self.name_edit.text().strip() or "未命名脚本"
        self.script.path = self.path_edit.text().strip().strip('"')
        self.script.update_url = self.url_edit.text().strip()
        self.store.save(self.settings)
        self.refresh_status()
        self.changed.emit()

    def _choose_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择脚本文件",
            str(Path(self.script.path).parent) if self.script.path else str(Path.home()),
            "脚本文件 (*.bat *.cmd *.exe *.py);;所有文件 (*.*)",
        )
        if not path:
            return
        self.path_edit.setText(path)
        if not self.name_edit.text().strip() or self.name_edit.text().strip() == "新脚本":
            self.name_edit.setText(Path(path).stem)
        self._save_fields()

    def refresh_status(self) -> None:
        exists = bool(self.script.path and Path(self.script.path).expanduser().is_file())
        self.status_label.setText("已找到脚本" if exists else "未选择有效脚本")
        self.status_label.setStyleSheet(f"color: {SUCCESS if exists else MUTED};")
        self.launch_button.setEnabled(exists)
        self.open_url_button.setEnabled(bool(self.script.update_url.strip()))

    def launch(self, show_notice: bool = True) -> LaunchResult:
        self._save_fields()
        result = launch_script(self.script)
        if show_notice:
            show_result(self, result)
        return result

    def open_update(self) -> LaunchResult:
        self._save_fields()
        result = open_update_url(self.script)
        show_result(self, result)
        return result
