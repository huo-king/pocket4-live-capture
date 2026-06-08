"""页面 2：照片 / 实况 选择弹层"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CaptureTypePage(QWidget):
    photo_selected = Signal()
    live_selected = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        self.hide()

        self._sheet = QWidget(self)
        self._sheet.setStyleSheet(
            "background-color: #2D2D2D; border-top-left-radius: 16px; "
            "border-top-right-radius: 16px;"
        )

        sheet_layout = QVBoxLayout(self._sheet)
        sheet_layout.setContentsMargins(24, 20, 24, 24)
        sheet_layout.setSpacing(16)

        title = QLabel("选择导出类型")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sheet_layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        photo_btn = QPushButton("照片")
        photo_btn.setMinimumHeight(72)
        photo_btn.clicked.connect(self._choose_photo)
        btn_row.addWidget(photo_btn)

        live_btn = QPushButton("实况")
        live_btn.setObjectName("accentButton")
        live_btn.setMinimumHeight(72)
        live_btn.clicked.connect(self._choose_live)
        btn_row.addWidget(live_btn)

        sheet_layout.addLayout(btn_row)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.hide_sheet)
        sheet_layout.addWidget(cancel_btn)

        self._animation: QPropertyAnimation | None = None

    def show_sheet(self) -> None:
        self.show()
        self.raise_()
        self._layout_sheet()
        self._animate_sheet(show=True)

    def hide_sheet(self) -> None:
        self._animate_sheet(show=False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_sheet()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._sheet.geometry().contains(event.position().toPoint()):
                self.hide_sheet()
                return
        super().mousePressEvent(event)

    def _layout_sheet(self) -> None:
        sheet_height = min(260, max(220, int(self.height() * 0.28)))
        hidden = QRect(0, self.height(), self.width(), sheet_height)
        self._sheet.setGeometry(hidden)

    def _animate_sheet(self, show: bool) -> None:
        if self._animation is not None:
            self._animation.stop()

        sheet_height = min(260, max(220, int(self.height() * 0.28)))
        hidden = QRect(0, self.height(), self.width(), sheet_height)
        visible = QRect(0, self.height() - sheet_height, self.width(), sheet_height)
        start = hidden if show else visible
        end = visible if show else hidden

        self._animation = QPropertyAnimation(self._sheet, b"geometry", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        if not show:
            self._animation.finished.connect(self._on_hide_finished)
        self._animation.start()

    def _on_hide_finished(self) -> None:
        if self._animation:
            self._animation.finished.disconnect(self._on_hide_finished)
        self.hide()
        self.cancelled.emit()

    def _choose_photo(self) -> None:
        self.hide()
        self.photo_selected.emit()

    def _choose_live(self) -> None:
        self.hide()
        self.live_selected.emit()
