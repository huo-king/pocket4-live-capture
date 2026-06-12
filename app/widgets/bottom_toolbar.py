"""底部工具栏 — PNG / JPEG 照片 + 截实况（双行自适应）"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.quality_enhance_service import (
    ENHANCE_TIER_OPTIONS,
    DEFAULT_ENHANCE_TIER,
    EnhanceMode,
    coerce_enhance_mode,
)

GITHUB_URL = "https://github.com/huo-king/pocket-live-capture/releases"


class BottomToolbar(QWidget):
    png_photo_clicked = Signal()
    jpeg_photo_clicked = Signal()
    live_clicked = Signal()
    batch_watermark_clicked = Signal()
    watermark_changed = Signal(bool)
    quality_enhance_changed = Signal(bool)
    quality_enhance_mode_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("bottomToolbar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.watermark_cb = QCheckBox("添加水印")
        self.watermark_cb.setObjectName("watermarkCheckBox")
        self.watermark_cb.setToolTip(
            "勾选后，导出 PNG / JPEG / 实况时自动叠加 OSMO POCKET 4 水印"
        )
        self.watermark_cb.toggled.connect(self.watermark_changed.emit)
        top_row.addWidget(self.watermark_cb)

        self.enhance_cb = QCheckBox("画质增强")
        self.enhance_cb.setObjectName("enhanceCheckBox")
        self.enhance_cb.setToolTip(
            "勾选后从下拉选择增强档位。\n"
            "不勾选 = 原画直出 / stream copy（最快）。"
        )
        self.enhance_cb.setChecked(False)
        self.enhance_cb.toggled.connect(self._on_enhance_toggled)
        top_row.addWidget(self.enhance_cb)

        self.enhance_combo = QComboBox()
        self.enhance_combo.setObjectName("enhanceModeCombo")
        self.enhance_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.enhance_combo.setMinimumWidth(160)
        self.enhance_combo.setVisible(False)
        for tier in ENHANCE_TIER_OPTIONS:
            self.enhance_combo.addItem(
                f"{tier.label} · {tier.subtitle}",
                tier.mode.value,
            )
        default_index = next(
            (
                i
                for i, tier in enumerate(ENHANCE_TIER_OPTIONS)
                if tier.mode == DEFAULT_ENHANCE_TIER
            ),
            1,
        )
        self.enhance_combo.setCurrentIndex(default_index)
        self.enhance_combo.currentIndexChanged.connect(self._emit_enhance_mode)
        top_row.addWidget(self.enhance_combo, stretch=1)
        top_row.addStretch()

        self.github_label = QLabel('<a href="#">📥 下载 / GitHub</a>')
        self.github_label.setObjectName("githubLink")
        self.github_label.setOpenExternalLinks(False)
        self.github_label.linkActivated.connect(self._open_github)
        self.github_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        top_row.addWidget(self.github_label)
        layout.addLayout(top_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.png_btn = self._make_action_button("PNG", "导出 PNG 无损截图")
        self.jpeg_btn = self._make_action_button("JPEG", "导出 JPEG 最高质量截图（PNG 无损中转）")
        self.live_btn = self._make_action_button("截实况", "")
        self.batch_btn = self._make_action_button(
            "批量水印", "为已有 PNG/JPEG/实况图批量添加水印"
        )
        self.live_btn.setObjectName("accentButton")

        self.png_btn.clicked.connect(self.png_photo_clicked.emit)
        self.jpeg_btn.clicked.connect(self.jpeg_photo_clicked.emit)
        self.live_btn.clicked.connect(self.live_clicked.emit)
        self.batch_btn.clicked.connect(self.batch_watermark_clicked.emit)

        for btn in (self.png_btn, self.jpeg_btn, self.live_btn, self.batch_btn):
            btn_row.addWidget(btn, stretch=1)
        layout.addLayout(btn_row)

    def _on_enhance_toggled(self, checked: bool) -> None:
        self.enhance_combo.setVisible(checked)
        self.enhance_combo.setEnabled(checked)
        self.quality_enhance_changed.emit(checked)
        self._emit_enhance_mode()

    def _emit_enhance_mode(self) -> None:
        self.quality_enhance_mode_changed.emit(self.get_enhance_mode())

    @staticmethod
    def _make_action_button(text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(40)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if tooltip:
            btn.setToolTip(tooltip)
        return btn

    @staticmethod
    def _open_github(_link: str) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_URL))

    def set_enabled(self, enabled: bool) -> None:
        self.watermark_cb.setEnabled(enabled)
        self.enhance_cb.setEnabled(enabled)
        self.enhance_combo.setEnabled(enabled and self.enhance_cb.isChecked())
        self.png_btn.setEnabled(enabled)
        self.jpeg_btn.setEnabled(enabled)
        self.live_btn.setEnabled(enabled)
        self.batch_btn.setEnabled(True)

    def is_watermark_enabled(self) -> bool:
        return self.watermark_cb.isChecked()

    def is_quality_enhance_enabled(self) -> bool:
        return self.enhance_cb.isChecked()

    def get_enhance_mode(self) -> EnhanceMode:
        if not self.enhance_cb.isChecked():
            return EnhanceMode.OFF
        mode = coerce_enhance_mode(self.enhance_combo.currentData())
        if mode is not None:
            return mode
        index = self.enhance_combo.currentIndex()
        if 0 <= index < len(ENHANCE_TIER_OPTIONS):
            return ENHANCE_TIER_OPTIONS[index].mode
        return DEFAULT_ENHANCE_TIER
