"""LUT 状态面板 — 显示当前 LUT 配置摘要。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.services.lut_service import LUT_DISABLED, LutConfig, describe_lut


class LutPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("lutPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.status_label = QLabel("LUT · 关闭")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.set_lut_config(LUT_DISABLED)

    def set_lut_config(self, config: LutConfig) -> None:
        text = describe_lut(config)
        if not config.enabled:
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: #666666; font-size: 12px;")
        elif not config.active:
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: #FFAA44; font-size: 12px;")
        else:
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: #4DA3FF; font-size: 12px;")
