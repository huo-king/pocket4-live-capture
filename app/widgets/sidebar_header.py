"""侧边栏顶部品牌区。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SidebarHeader(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebarHeader")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 8)
        layout.setSpacing(2)

        self.title_label = QLabel("Pocket")
        self.title_label.setObjectName("sidebarTitle")
        self.subtitle_label = QLabel("实况截图")
        self.subtitle_label.setObjectName("sidebarSubtitle")
        self.tagline_label = QLabel("Mimo 风格 · 无损导出")
        self.tagline_label.setObjectName("sidebarTagline")
        self.tagline_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.tagline_label)
