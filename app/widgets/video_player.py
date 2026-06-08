"""封装 QMediaPlayer + QVideoWidget"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".MP4", ".MOV", ".M4V"}


class ClickableVideoWidget(QVideoWidget):
    """点击画面切换播放/暂停。"""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class VideoPlayerWidget(QWidget):
    position_changed = Signal(int)
    duration_changed = Signal(int)
    playback_state_changed = Signal(bool)
    video_loaded = Signal(str)
    load_failed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._duration_ms = 0
        self._user_seeking = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = ClickableVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.video_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.video_widget.clicked.connect(self.toggle_playback)
        layout.addWidget(self.video_widget)

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self.video_widget)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.errorOccurred.connect(self._on_error)

    @property
    def player(self) -> QMediaPlayer:
        return self._player

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    def load(self, path: str) -> None:
        ext = Path(path).suffix
        if ext not in SUPPORTED_EXTENSIONS:
            self.load_failed.emit("不支持的格式，请使用 .mp4 / .mov")
            return

        url = QUrl.fromLocalFile(path)
        self._player.setSource(url)
        self.video_loaded.emit(path)

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def toggle_playback(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def current_position_ms(self) -> int:
        return self._player.position()

    def seek(self, position_ms: int) -> None:
        self._player.setPosition(max(0, position_ms))

    def set_user_seeking(self, seeking: bool) -> None:
        self._user_seeking = seeking

    def grab_current_frame(self):
        return self.video_widget.grab()

    def _on_position_changed(self, position: int) -> None:
        if not self._user_seeking:
            self.position_changed.emit(position)

    def _on_duration_changed(self, duration: int) -> None:
        self._duration_ms = duration
        self.duration_changed.emit(duration)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.playback_state_changed.emit(
            state == QMediaPlayer.PlaybackState.PlayingState
        )

    def _on_error(self, error: QMediaPlayer.Error, _message: str = "") -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        msg = self._player.errorString() or "视频无法播放"
        self.load_failed.emit(msg)
