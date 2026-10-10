"""启动页：游戏启动配置和多个独立脚本启动器。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from better_clx.services.settings import AppSettings, ScriptConfig, SettingsStore
from better_clx.ui.launcher_cards import GameLauncherCard, ScriptLauncherCard
from better_clx.ui.theme import CONTENT_MARGIN, MUTED


class EmptyScriptState(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(8)
        title = StrongBodyLabel("暂未配置脚本", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        hint = BodyLabel("点击“添加脚本”，为每个脚本配置独立的启动路径和更新网址。", self)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)


class StartPage(QWidget):
    """Keep game/script launch configuration separate from window binding."""

    binding_requested = Signal()

    def __init__(
        self,
        settings: AppSettings,
        settings_store: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("startPage")
        self.settings_store = settings_store
        self.settings = settings
        self._script_cards: dict[str, ScriptLauncherCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*CONTENT_MARGIN)
        root.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(12)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(SubtitleLabel("启动", self))
        subtitle = BodyLabel("启动游戏和脚本，窗口选择与绑定请前往绑定页面", self)
        subtitle.setStyleSheet(f"color: {MUTED};")
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch(1)
        self.binding_button = PushButton(FluentIcon.LINK, "绑定窗口", self)
        self.binding_button.clicked.connect(self.binding_requested)
        header.addWidget(self.binding_button)
        root.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.content = QWidget(scroll)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 8, 0)
        self.content_layout.setSpacing(14)
        scroll.setWidget(self.content)
        root.addWidget(scroll, 1)

        self._build_launch_section()
        self._build_script_section()
        self.content_layout.addStretch(1)

    def _build_launch_section(self) -> None:
        heading = QHBoxLayout()
        heading.addWidget(StrongBodyLabel("启动配置", self.content))
        heading.addWidget(CaptionLabel("游戏路径可手动填写，也可以 BFS 查找", self.content))
        heading.addStretch(1)
        self.content_layout.addLayout(heading)

        self.game_card = GameLauncherCard(self.settings, self.settings_store, self.content)
        self.content_layout.addWidget(self.game_card)

    def _build_script_section(self) -> None:
        heading = QHBoxLayout()
        heading.addWidget(StrongBodyLabel("脚本启动", self.content))
        heading.addWidget(CaptionLabel("每个脚本独立保存启动路径和更新网址", self.content))
        heading.addStretch(1)
        self.add_script_button = PushButton(FluentIcon.ADD, "添加脚本", self.content)
        self.add_script_button.clicked.connect(self.add_script)
        heading.addWidget(self.add_script_button)
        self.content_layout.addLayout(heading)

        self.script_host = QWidget(self.content)
        self.script_layout = QVBoxLayout(self.script_host)
        self.script_layout.setContentsMargins(0, 0, 0, 0)
        self.script_layout.setSpacing(10)
        self.content_layout.addWidget(self.script_host)
        self._render_scripts()

    def _clear_script_layout(self) -> None:
        while self.script_layout.count():
            item = self.script_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _render_scripts(self) -> None:
        self._clear_script_layout()
        self._script_cards.clear()
        if not self.settings.scripts:
            self.script_layout.addWidget(EmptyScriptState(self.script_host))
            return
        for script in self.settings.scripts:
            card = ScriptLauncherCard(script, self.settings, self.settings_store, self.script_host)
            card.changed.connect(self._on_script_changed)
            card.removed.connect(self.remove_script)
            self._script_cards[script.script_id] = card
            self.script_layout.addWidget(card)

    def _on_script_changed(self) -> None:
        self.settings_store.save(self.settings)

    def add_script(self) -> None:
        index = len(self.settings.scripts) + 1
        self.settings.scripts.append(ScriptConfig(name=f"脚本 {index}"))
        self.settings_store.save(self.settings)
        self._render_scripts()

    def remove_script(self, script_id: str) -> None:
        self.settings.scripts = [script for script in self.settings.scripts if script.script_id != script_id]
        self.settings_store.save(self.settings)
        self._render_scripts()
