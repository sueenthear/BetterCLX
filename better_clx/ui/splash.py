"""Startup splash screen shown while the main Qt window is being built."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from better_clx.config import APP_NAME

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_PATH = PROJECT_ROOT / "Background.jpg"


class StartupSplash(QWidget):
    """Frameless image splash with a stable bottom progress bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(760, 430)
        self._build_ui()

    def _build_ui(self) -> None:
        self.background = QLabel(self)
        self.background.setGeometry(self.rect())
        self.background.setScaledContents(True)
        pixmap = QPixmap(str(BACKGROUND_PATH))
        if not pixmap.isNull():
            self.background.setPixmap(pixmap)
        else:
            self.background.setStyleSheet("background: #20242b;")
        self.background.lower()

        overlay = QWidget(self)
        overlay.setGeometry(self.rect())
        overlay.setStyleSheet("background: rgba(0, 0, 0, 35);")
        root = QVBoxLayout(overlay)
        root.setContentsMargins(26, 24, 26, 22)
        root.addStretch(1)

        self.status_label = QLabel("正在启动 Better CLX…", overlay)
        self.status_label.setStyleSheet(
            "color: white; font-size: 15px; font-weight: 600; "
            "background: rgba(0, 0, 0, 95); padding: 8px 12px; border-radius: 4px;"
        )
        root.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.progress = QProgressBar(overlay)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,150); border: none; border-radius: 4px; }"
            "QProgressBar::chunk { background: #14b8a6; border-radius: 4px; }"
        )
        root.addWidget(self.progress)

    def update_progress(self, value: int, status: str) -> None:
        self.progress.setValue(max(0, min(100, value)))
        self.status_label.setText(status)
        QApplication.processEvents()
