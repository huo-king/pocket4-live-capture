"""原片 + LUT 并排对比视图。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.widgets.lut_compare_pane import LutComparePane
from app.widgets.video_player import VideoPlayerWidget


class _PaneHeader(QWidget):
    def __init__(
        self,
        text: str,
        *,
        object_name: str,
        badge_object_name: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFixedHeight(32)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)

        dot = QLabel("●")
        dot.setObjectName("videoCompareDot")
        dot.setFixedWidth(12)

        self.label = QLabel(text)
        self.label.setObjectName(badge_object_name)

        row.addWidget(dot)
        row.addWidget(self.label)
        row.addStretch()


class VideoCompareView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("videoCompareView")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left = QWidget()
        left.setObjectName("videoCompareLeft")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(
            _PaneHeader(
                "原片预览",
                object_name="videoCompareHeader",
                badge_object_name="videoCompareHeaderText",
            )
        )
        self.video_player = VideoPlayerWidget()
        self.video_player.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        left_layout.addWidget(self.video_player, stretch=1)

        self.lut_pane = LutComparePane()
        self.lut_pane.hide()

        layout.addWidget(left, stretch=3)
        layout.addWidget(self.lut_pane, stretch=2)

    def set_lut_compare_visible(self, visible: bool) -> None:
        self.lut_pane.setVisible(visible)

    @property
    def compare_active(self) -> bool:
        return self.lut_pane.isVisible()
