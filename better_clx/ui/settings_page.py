from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QRadioButton, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, CaptionLabel, StrongBodyLabel, SubtitleLabel, SwitchButton

from better_clx.services.settings import AppSettings, SettingsStore
from better_clx.ui.theme import CONTENT_MARGIN, MUTED


class SettingsPage(QWidget):
    settings_changed = Signal()

    def __init__(self, settings: AppSettings, store: SettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.settings = settings
        self.store = store
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*CONTENT_MARGIN)
        root.setSpacing(16)
        root.addWidget(SubtitleLabel("设置", self))

        automation = CardWidget(self)
        automation_layout = QVBoxLayout(automation)
        automation_layout.setContentsMargins(20, 18, 20, 18)
        automation_layout.setSpacing(14)
        automation_layout.addWidget(StrongBodyLabel("自动化行为", automation))
        automation_layout.addWidget(CaptionLabel("以下选项默认关闭，修改后立即保存。", automation))
        self.auto_launch_switch = self._add_switch(
            automation_layout,
            "启动 Better CLX 时自动启动游戏",
            "没有检测到游戏进程时，使用启动页配置启动游戏。",
            self.settings.auto_launch_game,
            self._set_auto_launch,
        )
        self.kill_games_switch = self._add_switch(
            automation_layout,
            "关闭 Better CLX 时结束所有游戏进程",
            "退出程序前结束 wyclx64.exe 和 wyclx.exe。",
            self.settings.kill_games_on_close,
            self._set_kill_games,
        )
        root.addWidget(automation)

        close_card = CardWidget(self)
        close_layout = QVBoxLayout(close_card)
        close_layout.setContentsMargins(20, 18, 20, 18)
        close_layout.setSpacing(10)
        close_layout.addWidget(StrongBodyLabel("关闭窗口行为", close_card))
        close_layout.addWidget(CaptionLabel("选择点击窗口关闭按钮后的行为。", close_card))
        self.close_group = QButtonGroup(self)
        options = (
            ("minimize", "最小化至托盘", "托盘菜单可以恢复或彻底退出。"),
            ("confirm", "弹出二次确认窗口", "默认行为，确认后才退出程序。"),
            ("exit", "直接关闭", "立即退出程序。"),
        )
        for value, title, hint in options:
            row = QHBoxLayout()
            radio = QRadioButton(title, close_card)
            radio.setProperty("closeBehavior", value)
            radio.setChecked(self.settings.close_behavior == value)
            radio.toggled.connect(lambda checked, selected=value: self._set_close_behavior(selected) if checked else None)
            self.close_group.addButton(radio)
            row.addWidget(radio)
            row.addWidget(CaptionLabel(hint, close_card), 1)
            close_layout.addLayout(row)
        root.addWidget(close_card)
        root.addStretch(1)

    def _add_switch(self, layout, title: str, hint: str, checked: bool, callback) -> SwitchButton:
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(BodyLabel(title, self))
        hint_label = CaptionLabel(hint, self)
        hint_label.setStyleSheet(f"color: {MUTED};")
        text.addWidget(hint_label)
        row.addLayout(text, 1)
        switch = SwitchButton("", self)
        switch.setOnText("")
        switch.setOffText("")
        switch.setMinimumWidth(58)
        switch.setChecked(checked)
        switch.checkedChanged.connect(callback)
        row.addWidget(switch)
        layout.addLayout(row)
        return switch

    def _save(self) -> None:
        self.store.save(self.settings)
        self.settings_changed.emit()

    def _set_auto_launch(self, value: bool) -> None:
        self.settings.auto_launch_game = value
        self._save()

    def _set_kill_games(self, value: bool) -> None:
        self.settings.kill_games_on_close = value
        self._save()

    def _set_close_behavior(self, value: str) -> None:
        self.settings.close_behavior = value
        self._save()
