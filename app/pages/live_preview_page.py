"""页面 3：实况预览 + 导出"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.capture_task import CaptureTask
from app.services.ffmpeg_service import FFmpegService
from app.services.quality_enhance_service import EnhanceMode, get_tier_option
from app.widgets.video_player import SUPPORTED_EXTENSIONS, VideoPlayerWidget


class LivePreviewPage(QWidget):
    export_clicked = Signal(CaptureTask)
    back_clicked = Signal()
    video_dropped = Signal(str)

    INDEX_VIDEO = 0
    INDEX_IMAGE = 1

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._task: CaptureTask | None = None
        self._source_image: QImage | None = None
        self._source_pil_image = None
        self._use_video_preview = False
        self._video_preview_ready = False

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

        title = QLabel("实况预览")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title, stretch=1)

        spacer = QWidget()
        spacer.setFixedWidth(self.back_btn.sizeHint().width())
        header_layout.addWidget(spacer)

        layout.addWidget(header)

        self.preview_stack = QStackedWidget()
        self.preview_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.video_player = VideoPlayerWidget()
        self.preview_stack.addWidget(self.video_player)

        self.image_label = QLabel("封面预览加载中…")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #000000; color: #888888;"
        )
        self.image_label.setScaledContents(False)
        self.preview_stack.addWidget(self.image_label)

        layout.addWidget(self.preview_stack, stretch=1)

        self._install_video_drop_targets()
        self.video_player.file_dropped.connect(self.video_dropped.emit)

        footer_info = QWidget()
        footer_info_layout = QVBoxLayout(footer_info)
        footer_info_layout.setContentsMargins(16, 8, 16, 8)
        footer_info_layout.setSpacing(6)

        self.hint_label = QLabel(
            "预览与播放页同源解码（无水印）或 PNG 原图（有水印）。"
            "导出时封面为 Motion Photo 要求的 JPEG，视频为 stream copy 原画。"
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #B0B0B0; font-size: 12px;")
        footer_info_layout.addWidget(self.hint_label)

        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setObjectName("timestampLabel")
        footer_info_layout.addWidget(self.info_label)

        layout.addWidget(footer_info, stretch=0)

        footer = QWidget()
        footer.setObjectName("bottomToolbar")
        footer.setFixedHeight(72)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()

        self.export_btn = QPushButton("导出实况")
        self.export_btn.setObjectName("accentButton")
        self.export_btn.setMinimumSize(160, 44)
        self.export_btn.clicked.connect(self._on_export)
        footer_layout.addWidget(self.export_btn)

        layout.addWidget(footer, stretch=0)

        self.video_player.video_loaded.connect(self._on_video_loaded_for_preview)

    def _install_video_drop_targets(self) -> None:
        targets = [self.preview_stack, self.image_label]
        for widget in targets:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    @staticmethod
    def _video_path_from_drop(event) -> str | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            path = url.toLocalFile()
            if Path(path).suffix in SUPPORTED_EXTENSIONS:
                return path
        return None

    def eventFilter(self, obj, event) -> bool:
        event_type = event.type()
        if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            mime = event.mimeData()
            if mime.hasUrls():
                for url in mime.urls():
                    if Path(url.toLocalFile()).suffix in SUPPORTED_EXTENSIONS:
                        event.acceptProposedAction()
                        return True
        elif event_type == QEvent.Type.Drop:
            path = self._video_path_from_drop(event)
            if path:
                self.video_dropped.emit(path)
                event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)

    def show_loading(
        self,
        task: CaptureTask,
        *,
        use_video_preview: bool = False,
        preview_video_path: str | None = None,
        apply_watermark: bool = False,
        apply_enhance: bool = False,
        enhance_mode: EnhanceMode = EnhanceMode.OFF,
    ) -> None:
        self._task = task
        self._source_image = None
        self._source_pil_image = None
        self._use_video_preview = use_video_preview
        self._video_preview_ready = False
        self.export_btn.setEnabled(False)
        self.back_btn.setEnabled(False)

        info = FFmpegService().probe(task.video_path)
        task.compute_clip_bounds(info.duration_sec)
        self._update_info()

        if use_video_preview:
            self.preview_stack.setCurrentIndex(self.INDEX_VIDEO)
            play_path = preview_video_path or task.video_path
            using_proxy = Path(play_path).resolve() != Path(task.video_path).resolve()
            if using_proxy:
                base = (
                    "预览：H.264 代理视频（Windows 可播）。"
                    "导出仍用原片截帧 + stream copy，画质不受影响。"
                )
            else:
                base = (
                    "预览：与播放页相同的视频解码（原画，秒开）。"
                    "导出时封面封装为 JPEG，视频 stream copy。"
                )
            if apply_enhance:
                tier = get_tier_option(enhance_mode)
                if tier is not None:
                    base += f" 已选「{tier.label}」：{tier.subtitle}。"
                else:
                    base += " 已开启画质增强。"
            self.hint_label.setText(base)
            self.video_player.load(play_path)
            return

        self.preview_stack.setCurrentIndex(self.INDEX_IMAGE)
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("正在截取 PNG 无损预览…")
        wm = "含水印" if apply_watermark else "无水印"
        self.hint_label.setText(
            f"预览：PNG 无损原图（{wm}）。"
            "画质增强仅在导出时生效，预览不做 AI 超分。"
            "导出时封面封装为 JPEG，视频 stream copy。"
        )

    def set_preview_from_file(self, task: CaptureTask, image_path: str) -> None:
        self._task = task
        self._use_video_preview = False
        self.preview_stack.setCurrentIndex(self.INDEX_IMAGE)

        from PIL import Image

        try:
            self._source_pil_image = Image.open(image_path).convert("RGBA")
            self._source_image = None
            self._refresh_image_preview()
        except OSError:
            self._source_pil_image = None
            reader = QImageReader(image_path)
            reader.setAutoTransform(True)
            image = reader.read()
            if image.isNull():
                self.image_label.setPixmap(QPixmap())
                self.image_label.setText("封面预览加载失败，仍可直接导出")
            else:
                self._source_image = image
                self._refresh_image_preview()

        self._update_info()
        self.export_btn.setEnabled(True)
        self.back_btn.setEnabled(True)

    def set_preview_failed(self, message: str) -> None:
        self.preview_stack.setCurrentIndex(self.INDEX_IMAGE)
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(f"封面预览失败\n{message}\n仍可尝试导出")
        if self._task:
            self.info_label.setText(
                f"暂停于 {_format_ms(self._task.timestamp_ms)} · 预览失败"
            )
        self.export_btn.setEnabled(True)
        self.back_btn.setEnabled(True)

    def _on_video_loaded_for_preview(self) -> None:
        if not self._use_video_preview or self._task is None:
            return
        self.video_player.seek(self._task.timestamp_ms)
        self.video_player.pause()
        self._video_preview_ready = True
        self.export_btn.setEnabled(True)
        self.back_btn.setEnabled(True)

    def _update_info(self) -> None:
        if self._task is None:
            return
        self.info_label.setText(
            f"暂停于 {_format_ms(self._task.timestamp_ms)} · "
            f"片段 {self._task.clip_duration_sec:.1f}s"
        )

    def _refresh_image_preview(self) -> None:
        dpr = self.devicePixelRatioF()
        label_w = max(1, int(self.image_label.width() * dpr))
        label_h = max(1, int(self.image_label.height() * dpr))

        if self._source_pil_image is not None:
            from PIL import Image
            from PIL.ImageQt import ImageQt

            src = self._source_pil_image
            src_w, src_h = src.size
            scale = min(label_w / src_w, label_h / src_h, 1.0)
            target_w = max(1, int(src_w * scale))
            target_h = max(1, int(src_h * scale))

            if scale < 1.0:
                display = src.resize((target_w, target_h), Image.Resampling.LANCZOS)
            else:
                display = src

            pixmap = QPixmap.fromImage(ImageQt(display))
            pixmap.setDevicePixelRatio(dpr)
            self.image_label.setPixmap(pixmap)
            self.image_label.setText("")
            return

        if self._source_image is None or self._source_image.isNull():
            return

        src_w = self._source_image.width()
        src_h = self._source_image.height()

        if src_w <= label_w and src_h <= label_h:
            scaled_image = self._source_image
        else:
            scaled_image = self._source_image.scaled(
                label_w,
                label_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        pixmap = QPixmap.fromImage(scaled_image)
        pixmap.setDevicePixelRatio(dpr)
        self.image_label.setPixmap(pixmap)
        self.image_label.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._use_video_preview:
            self._refresh_image_preview()

    def _on_export(self) -> None:
        if self._task is not None:
            self.export_clicked.emit(self._task)


def _format_ms(ms: int) -> str:
    total_sec = ms // 1000
    minutes = total_sec // 60
    seconds = total_sec % 60
    millis = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
