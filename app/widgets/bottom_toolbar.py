"""底部工具栏 — PNG / JPEG 照片 + 截实况（双行自适应）"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

GITHUB_URL = "https://github.com/huo-king/pocket-live-capture/releases"


class BottomToolbar(QWidget):
    png_photo_clicked = Signal()
    jpeg_photo_clicked = Signal()
    live_clicked = Signal()
    batch_watermark_clicked = Signal()
    watermark_changed = Signal(bool)

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
        self.png_btn.setEnabled(enabled)
        self.jpeg_btn.setEnabled(enabled)
        self.live_btn.setEnabled(enabled)
        self.batch_btn.setEnabled(True)

    def is_watermark_enabled(self) -> bool:
        return self.watermark_cb.isChecked()
