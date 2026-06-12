"""画质增强区域 — 档位说明"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.services.quality_enhance_service import (
    EnhanceMode,
    coerce_enhance_mode,
    get_tier_option,
    is_realesrgan_available,
    is_realesrgan_mode,
    resolve_export_enhance_mode,
)


class QualityEnhancePanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("qualityEnhancePanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)

        self.title_label = QLabel("画质")
        self.title_label.setObjectName("sectionTitle")
        layout.addWidget(self.title_label)

        self.status_label = QLabel("第 1 档 · 原画直出：不勾选「画质增强」，导出最快、无损 stream copy。")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666666; font-size: 13px;")
        layout.addWidget(self.status_label)

        self.set_enhance_mode(EnhanceMode.OFF)

    def set_enhance_enabled(self, enabled: bool) -> None:
        if not enabled:
            self.set_enhance_mode(EnhanceMode.OFF)

    def set_enhance_mode(self, mode: EnhanceMode | str) -> None:
        coerced = coerce_enhance_mode(mode)
        if coerced is None or coerced == EnhanceMode.OFF:
            self.status_label.setText(
                "第 1 档 · 原画直出：不勾选「画质增强」，导出最快、无损 stream copy。"
            )
            self.status_label.setStyleSheet("color: #666666; font-size: 13px;")
            return

        mode = coerced
        tier = get_tier_option(mode)
        if tier is None:
            self.status_label.setText("已开启画质增强")
            self.status_label.setStyleSheet("color: #4DA3FF; font-size: 13px;")
            return

        resolved = resolve_export_enhance_mode(mode)
        tier_index = {
            EnhanceMode.FFMPEG_LIGHT: 2,
            EnhanceMode.REALESRGAN_COVER: 3,
            EnhanceMode.REALESRGAN_FULL: 4,
        }.get(tier.mode, 0)

        text = f"第 {tier_index} 档 · {tier.label}：{tier.description}"
        if is_realesrgan_mode(mode) and not is_realesrgan_available():
            text += "（未检测到 Real-ESRGAN，导出时将回退为「轻度优化」）"
            self.status_label.setStyleSheet("color: #FFAA44; font-size: 13px;")
        elif resolved != mode:
            self.status_label.setStyleSheet("color: #FFAA44; font-size: 13px;")
        elif tier.mode == EnhanceMode.REALESRGAN_FULL:
            self.status_label.setStyleSheet("color: #FF8866; font-size: 13px;")
        else:
            self.status_label.setStyleSheet("color: #4DA3FF; font-size: 13px;")

        self.status_label.setText(text)
