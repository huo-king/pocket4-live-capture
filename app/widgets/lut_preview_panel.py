"""LUT 预览条 — 显示当前帧 LUT 效果缩略图。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class LutPreviewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("lutPreviewPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.title_label = QLabel("LUT 预览")
        self.title_label.setObjectName("sectionTitle")
        text_col.addWidget(self.title_label)

        self.status_label = QLabel("启用 LUT 后可预览当前帧效果")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666666; font-size: 12px;")
        text_col.addWidget(self.status_label)
        text_col.addStretch()
        layout.addLayout(text_col, stretch=1)

        self.preview_label = QLabel("预览")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(160, 90)
        self.preview_label.setMaximumSize(240, 135)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.preview_label.setStyleSheet(
            "background-color: #111111; border-radius: 6px; color: #555555;"
        )
        layout.addWidget(self.preview_label, stretch=0)

        self.hide()

    def set_loading(self, message: str = "正在生成 LUT 预览…") -> None:
        self.show()
        self.status_label.setText(
            f"{message} · 原片截帧 + lut3d（与导出同色算法，导出仍 rgb48le 无损）"
        )
        self.status_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("…")
        self.preview_label.setStyleSheet(
            "background-color: #111111; border-radius: 6px; color: #666666;"
        )

    def set_preview(self, image_path: str, *, lut_label: str) -> None:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.set_error("预览图加载失败")
            return
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setText("")
        self.preview_label.setPixmap(scaled)
        self.preview_label.setStyleSheet(
            "background-color: #111111; border-radius: 6px; "
            "border: 1px solid #4DA3FF;"
        )
        self.status_label.setText(
            f"{lut_label} · 当前帧 LUT 效果（导出仍无损，预览为 rgb24 加速）"
        )
        self.status_label.setStyleSheet("color: #4DA3FF; font-size: 12px;")
        self.show()

    def set_error(self, message: str) -> None:
        self.show()
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #FF8866; font-size: 12px;")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("失败")
        self.preview_label.setStyleSheet(
            "background-color: #111111; border-radius: 6px; color: #FF8866;"
        )

    def clear_preview(self) -> None:
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("")
        self.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        pix = self.preview_label.pixmap()
        if pix and not pix.isNull():
            scaled = pix.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
