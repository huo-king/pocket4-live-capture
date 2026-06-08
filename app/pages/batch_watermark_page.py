"""批量加水印页面 — 拖入已有照片 / 实况图"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.batch_watermark_service import collect_supported_files


class BatchWatermarkPage(QWidget):
    start_batch = Signal(list, str)
    back_clicked = Signal()
    pick_output_dir = Signal()
    pick_files = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._output_dir = str(Path.home() / "Pictures")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("background-color: #2D2D2D;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 16, 12)

        self.back_btn = QPushButton("← 返回")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        header_layout.addWidget(self.back_btn)

        title = QLabel("批量加水印")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title, stretch=1)

        spacer = QWidget()
        spacer.setFixedWidth(self.back_btn.sizeHint().width())
        header_layout.addWidget(spacer)
        layout.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(24, 24, 24, 16)
        body.setSpacing(12)

        hint = QLabel(
            "拖入或添加 PNG / JPEG 照片、MVIMG 实况图。\n"
            "输出保持原格式（PNG→PNG、JPEG→JPEG、实况→MVIMG）；"
            "实况仅重封装封面，视频字节原样复制。"
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #B0B0B0; font-size: 12px;")
        body.addWidget(hint)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(280)
        self.file_list.setStyleSheet(
            "background-color: #111111; border: 1px dashed #444; border-radius: 8px;"
        )
        body.addWidget(self.file_list, stretch=1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("添加文件")
        self.add_btn.clicked.connect(self.pick_files.emit)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.file_list.clear)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        body.addLayout(btn_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("输出目录:"))
        self.output_label = QLabel(self._output_dir)
        self.output_label.setWordWrap(True)
        self.output_label.setStyleSheet("color: #888888;")
        out_row.addWidget(self.output_label, stretch=1)
        self.out_btn = QPushButton("选择…")
        self.out_btn.clicked.connect(self.pick_output_dir.emit)
        out_row.addWidget(self.out_btn)
        body.addLayout(out_row)

        layout.addLayout(body, stretch=1)

        footer = QWidget()
        footer.setObjectName("bottomToolbar")
        footer.setFixedHeight(72)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()

        self.start_btn = QPushButton("开始批量加水印")
        self.start_btn.setObjectName("accentButton")
        self.start_btn.setMinimumSize(180, 44)
        self.start_btn.clicked.connect(self._on_start)
        footer_layout.addWidget(self.start_btn)
        layout.addWidget(footer, stretch=0)

    @property
    def output_dir(self) -> str:
        return self._output_dir

    def set_output_dir(self, path: str) -> None:
        self._output_dir = path
        self.output_label.setText(path)

    def add_files(self, paths: list[str]) -> None:
        existing = {self.file_list.item(i).text() for i in range(self.file_list.count())}
        for path in collect_supported_files(paths):
            text = str(path.resolve())
            if text not in existing:
                self.file_list.addItem(text)

    def file_paths(self) -> list[str]:
        return [self.file_list.item(i).text() for i in range(self.file_list.count())]

    def set_busy(self, busy: bool) -> None:
        self.start_btn.setEnabled(not busy)
        self.add_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.back_btn.setEnabled(not busy)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.add_files(paths)
        event.acceptProposedAction()

    def _on_start(self) -> None:
        paths = self.file_paths()
        if not paths:
            return
        self.start_batch.emit(paths, self._output_dir)
