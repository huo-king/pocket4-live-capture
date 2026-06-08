"""处理区域 — 导出提示与当前帧信息"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


class ProcessingPanel(QWidget):
    """视频下方的处理信息区。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("processingPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)

        self.title_label = QLabel("处理")
        self.title_label.setObjectName("sectionTitle")
        layout.addWidget(self.title_label)

        self.status_label = QLabel("拖入视频文件开始")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #888888; font-size: 13px;")
        layout.addWidget(self.status_label)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(self.detail_label)

    def set_idle(self) -> None:
        self.status_label.setText("拖入视频文件开始")
        self.status_label.setStyleSheet("color: #888888; font-size: 13px;")
        self.detail_label.setText("")

    def set_loading(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #888888; font-size: 13px;")
        self.detail_label.setText("")

    def set_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #FF6B6B; font-size: 13px;")
        self.detail_label.setText("")

    def set_ready(self, *, hint: str | None = None, timestamp_ms: int = 0) -> None:
        if hint:
            self.status_label.setText(hint)
        else:
            self.status_label.setText(
                "暂停到目标画面，然后选择 PNG / JPEG 或「截实况」"
            )
        self.status_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        self._update_detail(timestamp_ms)

    def set_timestamp(self, timestamp_ms: int) -> None:
        if self.detail_label.text():
            self._update_detail(timestamp_ms)

    def _update_detail(self, timestamp_ms: int) -> None:
        sec = max(0, timestamp_ms) / 1000.0
        self.detail_label.setText(
            f"当前帧 {sec:.2f}s · 实况导出将以该帧为中心 ±1.5 秒"
        )
