"""状态胶囊标签 — 处理区信息展示。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class StatusChip(QLabel):
    def __init__(
        self,
        text: str = "",
        *,
        variant: str = "default",
        parent=None,
    ):
        super().__init__(text, parent)
        self.setObjectName("statusChip")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_variant(variant)

    def set_variant(self, variant: str) -> None:
        self.setProperty("variant", variant)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_chip_text(self, text: str, *, variant: str | None = None) -> None:
        self.setText(text)
        self.setVisible(bool(text))
        if variant is not None:
            self.set_variant(variant)
