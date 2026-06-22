"""DJI 官方 LUT 下载对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.dji_lut_download import (
    CATEGORY_LABELS,
    DjiLutEntry,
    download_dji_lut,
    get_dji_lut_catalog_by_category,
    is_already_downloaded,
)


class DjiLutDownloadWorker(QThread):
    progress = Signal(str)
    finished_one = Signal(str, str)
    failed_one = Signal(str)
    all_done = Signal(int, int)

    def __init__(self, entries: list[DjiLutEntry], parent=None):
        super().__init__(parent)
        self.entries = entries
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        ok = 0
        fail = 0
        for entry in self.entries:
            if self._cancelled:
                break
            self.progress.emit(f"下载 {entry.display_name}…")
            try:
                path = download_dji_lut(entry)
                ok += 1
                self.finished_one.emit(entry.display_name, str(path))
            except Exception as exc:
                fail += 1
                self.failed_one.emit(f"{entry.display_name}: {exc}")
        self.all_done.emit(ok, fail)


class DjiLutDownloadDialog(QDialog):
    lut_downloaded = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("djiLutDownloadDialog")
        self.setWindowTitle("下载 DJI 官方色彩还原 LUT")
        self.setModal(True)
        self.resize(520, 560)

        self._entries: list[DjiLutEntry] = []
        self._checkboxes: dict[DjiLutEntry, QCheckBox] = {}
        self._badges: dict[DjiLutEntry, QLabel] = {}
        self._worker: DjiLutDownloadWorker | None = None
        self._downloaded_paths: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("下载 DJI 官方色彩还原 LUT")
        title.setObjectName("titleLabel")
        header_row.addWidget(title, stretch=1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        header_row.addWidget(close_btn)
        root.addLayout(header_row)

        intro = QLabel(
            "为您的 DJI 设备下载官方 D-Log / D-Log M 转 Rec.709 色彩还原 LUT。\n"
            "文件保存到 Pictures/PocketLiveCapture/luts/，下载后自动加入 LUT 列表。"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        root.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        for category, entries in get_dji_lut_catalog_by_category().items():
            if not entries:
                continue
            body_layout.addWidget(self._build_category_section(category, entries))

        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        self.status_label = QLabel("勾选需要下载的 LUT")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        root.addWidget(self.status_label)

        self.download_btn = QPushButton("下载选中")
        self.download_btn.setObjectName("djiLutDownloadBtn")
        self.download_btn.clicked.connect(self._on_download_clicked)
        root.addWidget(self.download_btn)

        self._refresh_download_button()

    def _build_category_section(
        self, category: str, entries: list[DjiLutEntry]
    ) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(CATEGORY_LABELS.get(category, category))
        label.setObjectName("djiLutCategoryLabel")
        layout.addWidget(label)

        for entry in entries:
            self._entries.append(entry)
            row = QWidget()
            row.setObjectName("djiLutItemRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 8, 10, 8)
            row_layout.setSpacing(8)

            cb = QCheckBox()
            cb.stateChanged.connect(self._refresh_download_button)
            self._checkboxes[entry] = cb
            row_layout.addWidget(cb, alignment=Qt.AlignmentFlag.AlignTop)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            name = QLabel(f"{entry.device} · {entry.display_name}")
            name.setObjectName("djiLutItemName")
            name.setWordWrap(True)
            text_col.addWidget(name)
            meta = QLabel(entry.description or f"{entry.log_type} · 33³")
            meta.setObjectName("djiLutItemMeta")
            text_col.addWidget(meta)
            row_layout.addLayout(text_col, stretch=1)

            badge = QLabel("已下载" if is_already_downloaded(entry) else "")
            badge.setObjectName("djiLutAlreadyBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            self._badges[entry] = badge
            row_layout.addWidget(badge)

            layout.addWidget(row)

        return section

    def _selected_entries(self) -> list[DjiLutEntry]:
        return [entry for entry, cb in self._checkboxes.items() if cb.isChecked()]

    def _refresh_download_button(self) -> None:
        count = len(self._selected_entries())
        self.download_btn.setText(f"下载选中 ({count} 个)" if count else "下载选中")
        self.download_btn.setEnabled(count > 0 and self._worker is None)

    def _on_download_clicked(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        self.download_btn.setEnabled(False)
        for cb in self._checkboxes.values():
            cb.setEnabled(False)
        self._downloaded_paths.clear()
        self._worker = DjiLutDownloadWorker(entries, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_one.connect(self._on_finished_one)
        self._worker.failed_one.connect(self._on_failed_one)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_progress(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_finished_one(self, _name: str, path: str) -> None:
        self._downloaded_paths.append(path)

    def _on_failed_one(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #FF8866; font-size: 11px;")

    def _on_all_done(self, ok: int, fail: int) -> None:
        for entry, badge in self._badges.items():
            if is_already_downloaded(entry):
                badge.setText("已下载")
        for cb in self._checkboxes.values():
            cb.setEnabled(True)
            cb.setChecked(False)
        self._worker = None
        self._refresh_download_button()
        if fail:
            self.status_label.setText(f"完成：成功 {ok} 个，失败 {fail} 个")
            self.status_label.setStyleSheet("color: #FF8866; font-size: 11px;")
        else:
            self.status_label.setText(f"已全部下载（{ok} 个）")
            self.status_label.setStyleSheet("color: #4DA3FF; font-size: 11px;")
        if self._downloaded_paths:
            self.lut_downloaded.emit(list(self._downloaded_paths))

    def closeEvent(self, event) -> None:
        if self._worker is not None:
            self._worker.cancel()
        super().closeEvent(event)
