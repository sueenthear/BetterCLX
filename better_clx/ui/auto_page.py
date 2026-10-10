from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, FluentIcon, IconWidget, StrongBodyLabel, SubtitleLabel

from better_clx.ui.theme import CONTENT_MARGIN, MUTED


class AutoPage(QWidget):
    """Placeholder for future automatic workflow configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("autoPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(*CONTENT_MARGIN)
        root.setSpacing(14)

        root.addWidget(SubtitleLabel("自动", self))
        icon = IconWidget(FluentIcon.SYNC, self)
        icon.setFixedSize(48, 48)
        root.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        title = StrongBodyLabel("开发中", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        hint = CaptionLabel("自动化流程配置将在后续版本提供。", self)
        hint.setStyleSheet(f"color: {MUTED};")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)
        root.addStretch(1)
