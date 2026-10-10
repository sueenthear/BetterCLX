"""关于页面。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, CaptionLabel, FluentIcon, IconWidget, PushButton, StrongBodyLabel, SubtitleLabel

from better_clx.config import APP_NAME, APP_VERSION
from better_clx.runtime_paths import resource_path
from better_clx.ui.theme import CONTENT_MARGIN, MUTED

REPOSITORY_URL = "https://github.com/sueenthear/BetterCLX"
STATIC_SITE_URL = "https://sueenthear.github.io/BetterCLX/"


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutPage")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*CONTENT_MARGIN)
        root.setSpacing(18)
        root.addWidget(SubtitleLabel("关于", self))

        details = CardWidget(self)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(24, 22, 24, 22)
        details_layout.setSpacing(14)

        identity = QHBoxLayout()
        identity.setSpacing(12)
        icon = IconWidget(QIcon(str(resource_path("icon.ico"))), details)
        icon.setFixedSize(36, 36)
        identity.addWidget(icon)
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title_block.addWidget(StrongBodyLabel(APP_NAME, details))
        version = CaptionLabel(f"版本 {APP_VERSION}", details)
        version.setStyleSheet(f"color: {MUTED};")
        title_block.addWidget(version)
        identity.addLayout(title_block)
        identity.addStretch(1)
        details_layout.addLayout(identity)

        description = BodyLabel(
            "一梦江湖多实例启动与窗口管理工具，支持窗口绑定、连招配置和脚本管理。",
            details,
        )
        description.setWordWrap(True)
        details_layout.addWidget(description)

        repository_row = QHBoxLayout()
        repository_row.setSpacing(10)
        repository_row.addWidget(CaptionLabel("项目仓库", details))
        repository_row.addStretch(1)
        self.repository_button = PushButton(FluentIcon.GITHUB, "GitHub 仓库", details)
        self.repository_button.setMinimumSize(140, 36)
        self.repository_button.clicked.connect(self.open_repository)
        repository_row.addWidget(self.repository_button)
        details_layout.addLayout(repository_row)

        site_row = QHBoxLayout()
        site_row.setSpacing(10)
        site_row.addWidget(CaptionLabel("项目主页", details))
        site_row.addStretch(1)
        self.site_button = PushButton(FluentIcon.GLOBE, "打开静态网页", details)
        self.site_button.setMinimumSize(140, 36)
        self.site_button.clicked.connect(self.open_static_site)
        site_row.addWidget(self.site_button)
        details_layout.addLayout(site_row)
        root.addWidget(details)
        root.addStretch(1)

    def open_repository(self) -> None:
        QDesktopServices.openUrl(QUrl(REPOSITORY_URL))

    def open_static_site(self) -> None:
        QDesktopServices.openUrl(QUrl(STATIC_SITE_URL))
