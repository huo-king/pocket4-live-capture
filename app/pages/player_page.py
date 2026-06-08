"""页面 1：视频播放 + 照片/截实况"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from app.widgets.player_bottom_panel import PlayerBottomPanel
from app.widgets.processing_panel import ProcessingPanel
from app.widgets.video_player import VideoPlayerWidget
from app.widgets.watermark_preview_panel import WatermarkPreviewPanel


class PlayerPage(QWidget):
    png_photo_clicked = Signal(int)
    jpeg_photo_clicked = Signal(int)
    live_clicked = Signal(int)
    batch_watermark_clicked = Signal()
    video_error = Signal(str)

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
        self.bottom_panel = PlayerBottomPanel()

        layout.addWidget(self.view_stack, stretch=1)
        layout.addWidget(self.processing_panel, stretch=0)
        layout.addWidget(self.watermark_panel, stretch=0)
        layout.addWidget(self.bottom_panel, stretch=0)

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
        self.bottom_panel.toolbar.set_enabled(False)

    def is_watermark_enabled(self) -> bool:
        return self.bottom_panel.toolbar.is_watermark_enabled()

    def load_video(self, path: str, *, hint: str | None = None) -> None:
        self._load_hint = hint
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
