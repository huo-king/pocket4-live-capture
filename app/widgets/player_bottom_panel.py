"""播放页底部固定控制区 — 时间轴 + 照片/截实况按钮"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from app.widgets.bottom_toolbar import BottomToolbar
from app.widgets.timeline_slider import TimelineSlider


class PlayerBottomPanel(QWidget):
    """固定在窗口底部的控制面板，高度随内容与 DPI 自适应。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("playerBottomPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.timeline = TimelineSlider()
        layout.addWidget(self.timeline)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #3A3A3A;")
        layout.addWidget(divider)

        self.toolbar = BottomToolbar()
        layout.addWidget(self.toolbar)
