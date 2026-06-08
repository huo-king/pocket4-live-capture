"""水印区域 — 水印开关与预览"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.services.photo_watermark import resolve_watermark_path


class WatermarkPreviewPanel(QWidget):
    """水印配置下方的预览区。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("watermarkPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        self.title_label = QLabel("水印")
        self.title_label.setObjectName("sectionTitle")
        text_col.addWidget(self.title_label)

        self.status_label = QLabel("导出时未叠加水印")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666666; font-size: 13px;")
        text_col.addWidget(self.status_label)
        text_col.addStretch()
        layout.addLayout(text_col, stretch=1)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(120, 28)
        self.preview_label.setMaximumSize(160, 40)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.preview_label.setStyleSheet(
            "background-color: #111111; border-radius: 4px;"
        )
        layout.addWidget(self.preview_label, stretch=0)

        self._load_preview_asset()

    def _load_preview_asset(self) -> None:
        try:
            path = resolve_watermark_path()
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                return
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
        except FileNotFoundError:
            self.preview_label.setText("无预览")
            self.preview_label.setStyleSheet(
                "background-color: #111111; border-radius: 4px; color: #666666;"
            )

    def set_watermark_enabled(self, enabled: bool) -> None:
        if enabled:
            self.status_label.setText("导出 PNG / JPEG / 实况时将叠加 OSMO POCKET 4 水印")
            self.status_label.setStyleSheet("color: #4DA3FF; font-size: 13px;")
            self.preview_label.setStyleSheet(
                "background-color: #111111; border-radius: 4px; "
                "border: 1px solid #4DA3FF;"
            )
        else:
            self.status_label.setText("导出时未叠加水印")
            self.status_label.setStyleSheet("color: #666666; font-size: 13px;")
            self.preview_label.setStyleSheet(
                "background-color: #111111; border-radius: 4px;"
            )
