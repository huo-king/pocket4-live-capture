"""处理区域 — 导出提示与当前帧信息"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.widgets.status_chip import StatusChip


class ProcessingPanel(QWidget):
    """视频下方的处理信息区。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("processingPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        accent = QWidget()
        accent.setObjectName("processingAccentBar")
        accent.setFixedSize(4, 28)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel("工作台")
        self.title_label.setObjectName("sectionTitle")
        self.subtitle_label = QLabel("当前视频处理状态")
        self.subtitle_label.setObjectName("sectionSubtitle")
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)

        header_row.addWidget(accent, alignment=Qt.AlignmentFlag.AlignTop)
        header_row.addLayout(title_col, stretch=1)
        layout.addLayout(header_row)

        self.status_label = QLabel("拖入视频文件开始")
        self.status_label.setObjectName("processingStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self.chip_watermark = StatusChip("水印 · 关")
        self.chip_quality = StatusChip("画质 · 原画")
        self.chip_lut = StatusChip("LUT · 关", variant="default")
        for chip in (self.chip_watermark, self.chip_quality, self.chip_lut):
            chip_row.addWidget(chip)
        chip_row.addStretch()
        layout.addLayout(chip_row)

        self.detail_label = QLabel("")
        self.detail_label.setObjectName("processingDetail")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self.counter_label = QLabel("")
        self.counter_label.setObjectName("processingCounter")
        self.counter_label.setWordWrap(True)
        layout.addWidget(self.counter_label)

        self._watermark_on = False
        self._quality_text = ""
        self._lut_text = ""

    def _set_status_state(self, state: str) -> None:
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_idle(self) -> None:
        self.status_label.setText("拖入 MP4 / MOV 到窗口任意位置，即可开始截帧与导出")
        self._set_status_state("idle")
        self.detail_label.setText("")
        self.counter_label.setText("")
        self.chip_watermark.set_chip_text("水印 · 关")
        self.chip_quality.set_chip_text("画质 · 原画")
        self.chip_lut.set_chip_text("LUT · 关")

    def set_loading(self, message: str) -> None:
        self.status_label.setText(message)
        self._set_status_state("loading")
        self.detail_label.setText("")
        self.counter_label.setText("")

    def set_error(self, message: str) -> None:
        self.status_label.setText(message)
        self._set_status_state("error")
        self.detail_label.setText("")
        self.counter_label.setText("")

    def set_ready(self, *, hint: str | None = None, timestamp_ms: int = 0) -> None:
        if hint:
            self.status_label.setText(hint)
        else:
            self.status_label.setText(
                "已就绪 · 左侧设置画质 / LUT，右侧截取 PNG / JPEG / 实况"
            )
        self._set_status_state("ready")
        self._update_detail(timestamp_ms)

    def set_timestamp(self, timestamp_ms: int) -> None:
        if self.status_label.property("state") == "ready":
            self._update_detail(timestamp_ms)

    def set_export_counter(
        self,
        *,
        normal_seq: int,
        enhanced_seq: int,
        example_name: str = "",
    ) -> None:
        if normal_seq <= 0 and enhanced_seq <= 0:
            self.counter_label.setText("")
            return
        example = f" · 下次 {example_name}" if example_name else ""
        self.counter_label.setText(
            f"导出序号  普通 {normal_seq:03d}  /  增强 {enhanced_seq:03d}"
            f"  ·  增强含 _enh 后缀{example}"
        )

    def set_watermark_enabled(self, enabled: bool) -> None:
        self._watermark_on = enabled
        self._refresh_meta()

    def set_quality_summary(self, text: str) -> None:
        self._quality_text = text
        self._refresh_meta()

    def set_lut_summary(self, text: str) -> None:
        self._lut_text = text
        self._refresh_meta()

    def _refresh_meta(self) -> None:
        self.chip_watermark.set_chip_text(
            "水印 · 开" if self._watermark_on else "水印 · 关",
            variant="active" if self._watermark_on else "default",
        )
        quality = self._quality_text or "画质 · 原画"
        short = quality.split("：", 1)[-1][:20]
        is_off = "关闭" in quality or "原画" in short
        self.chip_quality.set_chip_text(
            short if short else "画质 · 原画",
            variant="default" if is_off else "accent",
        )
        lut = self._lut_text or "LUT · 关"
        short_lut = lut.split("·", 1)[-1].strip()[:24]
        lut_on = "关闭" not in lut and "文件缺失" not in lut
        self.chip_lut.set_chip_text(
            f"LUT · {short_lut}" if lut_on else "LUT · 关",
            variant="warm" if lut_on else "default",
        )

    def _update_detail(self, timestamp_ms: int) -> None:
        sec = max(0, timestamp_ms) / 1000.0
        self.detail_label.setText(
            f"时间轴  {sec:05.2f}s  ·  实况将以该帧为中心 ±1.5 秒"
        )
