"""底部时间轴滑块 + 时间显示"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def format_time_ms(ms: int, *, precise: bool = False) -> str:
    total_sec = max(0, ms) / 1000.0
    minutes = int(total_sec // 60)
    seconds = total_sec % 60
    if precise:
        return f"{minutes:02d}:{seconds:05.2f}"
    return f"{minutes:02d}:{int(seconds):02d}"


class TimelineSlider(QWidget):
    seek_started = Signal()
    seek_released = Signal(int)
    position_changed = Signal(int)

    _WHEEL_STEP_MS = 100
    _WHEEL_FINE_STEP_MS = 33

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._duration_ms = 0
        self._dragging = False

        self.setMinimumHeight(76)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("playButton")
        self.play_btn.setFixedSize(44, 44)
        top_row.addWidget(self.play_btn)

        self.position_label = QLabel("00:00")
        self.position_label.setObjectName("timelinePositionLabel")
        self.position_label.setMinimumWidth(72)
        top_row.addWidget(self.position_label)

        top_row.addStretch()

        self.duration_label = QLabel("/ 00:00")
        self.duration_label.setObjectName("timelineDurationLabel")
        self.duration_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        top_row.addWidget(self.duration_label)
        layout.addLayout(top_row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("timelineSlider")
        self.slider.setMinimumHeight(36)
        self.slider.setTracking(True)
        self.slider.setSingleStep(self._WHEEL_FINE_STEP_MS)
        self.slider.setPageStep(1000)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(self._on_seek_started)
        self.slider.sliderReleased.connect(self._emit_seek_released)
        self.slider.valueChanged.connect(self._on_value_changed)
        self.slider.installEventFilter(self)
        layout.addWidget(self.slider)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.slider and event.type() == event.Type.Wheel:
            self._on_wheel(event)
            return True
        return super().eventFilter(obj, event)

    def _on_wheel(self, event) -> None:
        if self._duration_ms <= 0:
            return
        step = (
            self._WHEEL_FINE_STEP_MS
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            else self._WHEEL_STEP_MS
        )
        delta = event.angleDelta().y()
        if delta == 0:
            return
        direction = 1 if delta > 0 else -1
        new_value = max(
            0,
            min(self._duration_ms, self.slider.value() + direction * step),
        )
        if new_value == self.slider.value():
            return
        self.slider.setValue(new_value)
        self.position_changed.emit(new_value)
        self.seek_released.emit(new_value)

    def set_duration(self, duration_ms: int) -> None:
        self._duration_ms = max(0, duration_ms)
        self.slider.setRange(0, self._duration_ms)
        self._update_labels(self.slider.value())

    def set_position(self, position_ms: int, *, block_signal: bool = True) -> None:
        position_ms = max(0, min(position_ms, self._duration_ms))
        if block_signal:
            self.slider.blockSignals(True)
        self.slider.setValue(position_ms)
        if block_signal:
            self.slider.blockSignals(False)
        self._update_labels(position_ms)

    def set_playing(self, playing: bool) -> None:
        self.play_btn.setText("⏸" if playing else "▶")

    def _on_seek_started(self) -> None:
        self._dragging = True
        self._update_labels(self.slider.value())
        self.seek_started.emit()

    def _on_value_changed(self, value: int) -> None:
        self._update_labels(value)
        if self.slider.isSliderDown():
            self.position_changed.emit(value)

    def _emit_seek_released(self) -> None:
        self._dragging = False
        self._update_labels(self.slider.value())
        self.seek_released.emit(self.slider.value())

    def _update_labels(self, position_ms: int) -> None:
        precise = self._dragging or self.slider.isSliderDown()
        self.position_label.setText(format_time_ms(position_ms, precise=precise))
        self.duration_label.setText(
            f"/ {format_time_ms(self._duration_ms, precise=precise)}"
        )
