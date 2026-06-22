"""播放页底部 — 时间轴"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.widgets.timeline_slider import TimelineSlider


class PlayerBottomPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("playerBottomPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.timeline = TimelineSlider()
        layout.addWidget(self.timeline)

        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(18, 0, 18, 10)
        hint = QLabel("Shift + 滚轮  精细 seek  ·  滚轮  逐帧步进")
        hint.setObjectName("timelineHint")
        hint_row.addWidget(hint)
        hint_row.addStretch()
        layout.addLayout(hint_row)
