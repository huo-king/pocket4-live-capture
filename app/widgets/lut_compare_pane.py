"""LUT 并排对比窗 — 原片右侧显示 LUT 效果。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.widgets.pixmap_util import fit_pixmap_to_widget


class LutComparePane(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("lutComparePane")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.badge = QLabel("LUT 预览")
        self.badge.setObjectName("lutCompareBadge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedHeight(28)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #000000;")
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.status_label = QLabel("启用「画面预览」后显示 LUT 对比")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self.status_label.setStyleSheet(
            "color: #666666; font-size: 11px; padding: 8px 12px;"
        )

        layout.addWidget(self.badge)
        layout.addWidget(self.preview_label, stretch=1)
        layout.addWidget(self.status_label, stretch=0)

    def set_loading(self, message: str = "正在生成 LUT 预览…") -> None:
        self._pixmap = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("…")
        self.preview_label.setStyleSheet(
            "background-color: #000000; color: #666666; font-size: 24px;"
        )
        self.status_label.setText(
            f"{message} · 原片截帧 + lut3d（Lanczos 限幅，导出仍无损）"
        )
        self.status_label.setStyleSheet(
            "color: #888888; font-size: 11px; padding: 8px 12px;"
        )

    def set_preview(self, image_path: str, *, lut_label: str) -> None:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.set_error("预览图加载失败")
            return
        self._pixmap = pixmap
        self.preview_label.setText("")
        self._refresh_pixmap()
        self.status_label.setText(f"{lut_label} · 与左侧同帧对比")
        self.status_label.setStyleSheet(
            "color: #4DA3FF; font-size: 11px; padding: 8px 12px;"
        )

    def set_error(self, message: str) -> None:
        self._pixmap = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("失败")
        self.preview_label.setStyleSheet(
            "background-color: #000000; color: #FF8866; font-size: 18px;"
        )
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            "color: #FF8866; font-size: 11px; padding: 8px 12px;"
        )

    def clear_preview(self) -> None:
        self._pixmap = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("")
        self.preview_label.setStyleSheet("background-color: #000000;")
        self.status_label.setText("启用「画面预览」后显示 LUT 对比")
        self.status_label.setStyleSheet(
            "color: #666666; font-size: 11px; padding: 8px 12px;"
        )

    def has_preview(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        self.preview_label.setPixmap(
            fit_pixmap_to_widget(self._pixmap, self.preview_label)
        )
