"""页面 1：视频播放 + 照片/截实况"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from app.services.quality_enhance_service import EnhanceMode, resolve_export_enhance_mode
from app.widgets.player_bottom_panel import PlayerBottomPanel
from app.widgets.processing_panel import ProcessingPanel
from app.widgets.quality_enhance_panel import QualityEnhancePanel
from app.widgets.video_player import SUPPORTED_EXTENSIONS, VideoPlayerWidget
from app.widgets.watermark_preview_panel import WatermarkPreviewPanel


class PlayerPage(QWidget):
    png_photo_clicked = Signal(int)
    jpeg_photo_clicked = Signal(int)
    live_clicked = Signal(int)
    batch_watermark_clicked = Signal()
    video_error = Signal(str)
    video_dropped = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._has_video = False
        self._load_hint: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.hint_label = QLabel("拖入视频文件开始")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #666666; font-size: 18px;")

        self.video_player = VideoPlayerWidget()
        self.video_player.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.view_stack = QStackedWidget()
        self.view_stack.setObjectName("videoStack")
        self.view_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.view_stack.addWidget(self.hint_label)
        self.view_stack.addWidget(self.video_player)

        self.processing_panel = ProcessingPanel()
        self.watermark_panel = WatermarkPreviewPanel()
        self.quality_panel = QualityEnhancePanel()
        self.bottom_panel = PlayerBottomPanel()

        layout.addWidget(self.view_stack, stretch=1)
        layout.addWidget(self.processing_panel, stretch=0)
        layout.addWidget(self.watermark_panel, stretch=0)
        layout.addWidget(self.quality_panel, stretch=0)
        layout.addWidget(self.bottom_panel, stretch=0)

        self._install_video_drop_targets()

        self.video_player.file_dropped.connect(self.video_dropped.emit)

        self.bottom_panel.timeline.play_btn.clicked.connect(
            self.video_player.toggle_playback
        )
        self.bottom_panel.timeline.seek_started.connect(
            lambda: self.video_player.set_user_seeking(True)
        )
        self.bottom_panel.timeline.seek_released.connect(self._on_seek_released)
        self.bottom_panel.timeline.position_changed.connect(self.video_player.seek)

        self.video_player.position_changed.connect(
            self.bottom_panel.timeline.set_position
        )
        self.video_player.position_changed.connect(
            self.processing_panel.set_timestamp
        )
        self.video_player.duration_changed.connect(
            self.bottom_panel.timeline.set_duration
        )
        self.video_player.playback_state_changed.connect(
            self.bottom_panel.timeline.set_playing
        )
        self.video_player.video_loaded.connect(self._on_video_loaded)
        self.video_player.load_failed.connect(self._on_load_failed)

        self.bottom_panel.toolbar.png_photo_clicked.connect(self._on_png_photo)
        self.bottom_panel.toolbar.jpeg_photo_clicked.connect(self._on_jpeg_photo)
        self.bottom_panel.toolbar.live_clicked.connect(self._on_live)
        self.bottom_panel.toolbar.batch_watermark_clicked.connect(
            self.batch_watermark_clicked.emit
        )
        self.bottom_panel.toolbar.watermark_changed.connect(
            self.watermark_panel.set_watermark_enabled
        )
        self.bottom_panel.toolbar.quality_enhance_changed.connect(
            self._on_quality_enhance_toggled
        )
        self.bottom_panel.toolbar.quality_enhance_mode_changed.connect(
            self.quality_panel.set_enhance_mode
        )
        self.bottom_panel.toolbar.set_enabled(False)

    def _install_video_drop_targets(self) -> None:
        """处理/水印等区域拖放；视频画面由 VideoPlayerWidget 透明层接管。"""
        targets = [
            self,
            self.view_stack,
            self.hint_label,
            self.processing_panel,
            self.watermark_panel,
            self.quality_panel,
            self.bottom_panel,
        ]
        for widget in targets:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)
        for child in self.findChildren(QWidget):
            if child is self.video_player:
                continue
            if self.video_player.isAncestorOf(child):
                continue
            child.setAcceptDrops(True)
            child.installEventFilter(self)

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

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._video_path_from_drop(event):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._video_path_from_drop(event)
        if path:
            self.video_dropped.emit(path)
            event.acceptProposedAction()

    def is_watermark_enabled(self) -> bool:
        return self.bottom_panel.toolbar.is_watermark_enabled()

    def is_quality_enhance_enabled(self) -> bool:
        return self.get_enhance_mode() != EnhanceMode.OFF

    def get_enhance_mode(self) -> EnhanceMode:
        mode = self.bottom_panel.toolbar.get_enhance_mode()
        return resolve_export_enhance_mode(mode)

    def _on_quality_enhance_toggled(self, enabled: bool) -> None:
        if enabled:
            self.quality_panel.set_enhance_mode(
                self.bottom_panel.toolbar.get_enhance_mode()
            )
        else:
            self.quality_panel.set_enhance_mode(EnhanceMode.OFF)

    def load_video(self, path: str, *, hint: str | None = None) -> None:
        self._load_hint = hint
        self._has_video = False
        self.view_stack.setCurrentWidget(self.video_player)
        self.hint_label.setText("正在加载视频…")
        self.hint_label.setStyleSheet("color: #888888; font-size: 16px;")
        self.processing_panel.set_loading("正在加载视频…")
        self.bottom_panel.timeline.set_duration(0)
        self.bottom_panel.timeline.set_position(0)
        self.bottom_panel.toolbar.set_enabled(False)
        self.video_player.load(path)

    def show_loading_message(self, message: str) -> None:
        self._has_video = False
        self.hint_label.setText(message)
        self.hint_label.setStyleSheet("color: #888888; font-size: 16px;")
        self.view_stack.setCurrentWidget(self.hint_label)
        self.processing_panel.set_loading(message)
        self.bottom_panel.toolbar.set_enabled(False)

    def show_load_error(self, message: str) -> None:
        self._on_load_failed(message)

    def current_timestamp_ms(self) -> int:
        return self.video_player.current_position_ms()

    def grab_preview_frame(self):
        return self.video_player.grab_current_frame()

    def _on_video_loaded(self, _path: str) -> None:
        self._has_video = True
        self.view_stack.setCurrentWidget(self.video_player)
        self.processing_panel.set_ready(
            hint=self._load_hint,
            timestamp_ms=self.current_timestamp_ms(),
        )
        self.bottom_panel.toolbar.set_enabled(True)
        self.video_player.play()

    def _on_load_failed(self, message: str) -> None:
        self._has_video = False
        self.hint_label.setText(message)
        self.hint_label.setStyleSheet("color: #FF6B6B; font-size: 16px;")
        self.view_stack.setCurrentWidget(self.hint_label)
        self.processing_panel.set_error(message)
        self.bottom_panel.toolbar.set_enabled(False)
        self.video_error.emit(message)

    def _on_seek_released(self, position_ms: int) -> None:
        self.video_player.set_user_seeking(False)
        self.video_player.seek(position_ms)

    def _prepare_capture(self) -> int | None:
        if not self._has_video:
            return None
        self.video_player.pause()
        return self.current_timestamp_ms()

    def _on_png_photo(self) -> None:
        ts = self._prepare_capture()
        if ts is not None:
            self.png_photo_clicked.emit(ts)

    def _on_jpeg_photo(self) -> None:
        ts = self._prepare_capture()
        if ts is not None:
            self.jpeg_photo_clicked.emit(ts)

    def _on_live(self) -> None:
        ts = self._prepare_capture()
        if ts is not None:
            self.live_clicked.emit(ts)
