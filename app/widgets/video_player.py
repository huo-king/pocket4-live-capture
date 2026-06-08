"""封装 QMediaPlayer + QVideoWidget"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".MP4", ".MOV", ".M4V"}


def _video_path_from_mime(mime) -> str | None:
    if not mime.hasUrls():
        return None
    for url in mime.urls():
        path = url.toLocalFile()
        if Path(path).suffix in SUPPORTED_EXTENSIONS:
            return path
    return None


class VideoDropOverlay(QWidget):
    """覆盖在视频上的透明层 — 接管点击与拖放（绕过 QVideoWidget 原生窗口）。"""

    file_dropped = Signal(str)
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _video_path_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if _video_path_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = _video_path_from_mime(event.mimeData())
        if path:
            self.file_dropped.emit(path)
            event.acceptProposedAction()


class ClickableVideoWidget(QVideoWidget):
    """点击画面切换播放/暂停。"""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, False)

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
    file_dropped = Signal(str)

    _LOAD_TIMEOUT_MS = 1500

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._duration_ms = 0
        self._user_seeking = False
        self._pending_path: str | None = None
        self._load_generation = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = ClickableVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")
        layout.addWidget(self.video_widget)

        self.drop_overlay = VideoDropOverlay(self)
        self.drop_overlay.clicked.connect(self.toggle_playback)
        self.drop_overlay.file_dropped.connect(self.file_dropped.emit)

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self.video_widget)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.drop_overlay.setGeometry(self.rect())
        self.drop_overlay.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.drop_overlay.setGeometry(self.rect())
        self.drop_overlay.raise_()

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

        resolved = str(Path(path).resolve())
        self._load_generation += 1
        generation = self._load_generation
        self._pending_path = resolved
        self._duration_ms = 0
        self._user_seeking = False
        self.duration_changed.emit(0)
        self.position_changed.emit(0)

        self._player.stop()
        self._player.setSource(QUrl())
        QTimer.singleShot(0, lambda: self._apply_source(resolved, generation))

    def _apply_source(self, resolved: str, generation: int) -> None:
        if generation != self._load_generation or self._pending_path != resolved:
            return
        self._player.setSource(QUrl.fromLocalFile(resolved))
        QTimer.singleShot(
            self._LOAD_TIMEOUT_MS,
            lambda: self._finish_load_if_pending(resolved, generation),
        )

    def _finish_load_if_pending(self, resolved: str, generation: int) -> None:
        if generation != self._load_generation or self._pending_path != resolved:
            return
        status = self._player.mediaStatus()
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.LoadingMedia,
        ):
            self._emit_video_loaded(resolved)

    def _emit_video_loaded(self, path: str) -> None:
        if self._pending_path is None:
            return
        self._pending_path = None
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

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if self._pending_path is None:
            return

        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            path = self._pending_path
            self._emit_video_loaded(path)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            if self._player.source().isEmpty():
                return
            self._pending_path = None
            msg = self._player.errorString() or "视频无法播放"
            self.load_failed.emit(msg)

    def _on_error(self, error: QMediaPlayer.Error, _message: str = "") -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        self._pending_path = None
        msg = self._player.errorString() or "视频无法播放"
        self.load_failed.emit(msg)
