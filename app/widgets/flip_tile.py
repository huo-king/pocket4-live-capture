"""可翻转功能磁贴 — 正面标题，背面功能控件。"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class FlipTile(QFrame):
    """点击正面翻转至背面；再次点击标题栏返回。"""

    flipped_changed = Signal(bool)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        accent: str = "#4DA3FF",
        icon: str = "◆",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("flipTile")
        self.setProperty("accent", accent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(188)
        self._flipped = False
        self._flip_progress = 0.0
        self._accent = accent

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("flipTileStack")
        outer.addWidget(self.stack)

        self._front = QFrame()
        self._front.setObjectName("flipTileFront")
        self._front.setProperty("accent", accent)
        front_layout = QVBoxLayout(self._front)
        front_layout.setContentsMargins(10, 14, 10, 12)
        front_layout.setSpacing(6)

        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName("flipTileIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedHeight(28)
        self.icon_label.setStyleSheet(
            f"color: {accent}; font-size: 16px; font-weight: bold;"
        )
        front_layout.addWidget(self.icon_label)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("flipTileTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        front_layout.addWidget(self.title_label)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("flipTileSubtitle")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setWordWrap(True)
            front_layout.addWidget(sub)
            self.subtitle_label = sub
        else:
            self.subtitle_label = None

        front_layout.addStretch()
        self.stack.addWidget(self._front)

        self._back = QFrame()
        self._back.setObjectName("flipTileBack")
        self._back.setProperty("accent", accent)
        self._back_layout = QVBoxLayout(self._back)
        self._back_layout.setContentsMargins(6, 6, 6, 6)
        self._back_layout.setSpacing(4)

        self._back_header = QLabel(f"← {title}")
        self._back_header.setObjectName("flipTileBackHeader")
        self._back_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_layout.addWidget(self._back_header)
        self.stack.addWidget(self._back)

        self._front.mousePressEvent = self._on_front_clicked  # type: ignore[method-assign]
        self._back_header.mousePressEvent = self._on_back_header_clicked  # type: ignore[method-assign]

        self._front_opacity = QGraphicsOpacityEffect(self._front)
        self._front.setGraphicsEffect(self._front_opacity)
        self._back_opacity = QGraphicsOpacityEffect(self._back)
        self._back.setGraphicsEffect(self._back_opacity)
        self._back_opacity.setOpacity(0.0)

        self._anim_group: QParallelAnimationGroup | None = None

    def set_subtitle(self, text: str) -> None:
        if self.subtitle_label is not None:
            self.subtitle_label.setText(text)
            self.subtitle_label.setVisible(bool(text))

    def set_back_widget(self, widget: QWidget) -> None:
        while self._back_layout.count() > 1:
            item = self._back_layout.takeAt(1)
            if item and item.widget():
                item.widget().setParent(None)
        self._back_layout.addWidget(widget, stretch=1)

    def is_flipped(self) -> bool:
        return self._flipped

    def set_flipped(self, flipped: bool, *, animate: bool = True) -> None:
        if flipped == self._flipped:
            return
        self._flipped = flipped
        self.flipped_changed.emit(flipped)
        if animate:
            self._run_flip_animation(flipped)
        else:
            self.stack.setCurrentWidget(self._back if flipped else self._front)
            self._front_opacity.setOpacity(0.0 if flipped else 1.0)
            self._back_opacity.setOpacity(1.0 if flipped else 0.0)

    def _on_front_clicked(self, _event) -> None:
        self.set_flipped(True)

    def _on_back_header_clicked(self, _event) -> None:
        self.set_flipped(False)

    def _run_flip_animation(self, to_back: bool) -> None:
        if self._anim_group is not None:
            self._anim_group.stop()

        self.stack.setCurrentWidget(self._back if to_back else self._front)
        start = self._flip_progress
        end = 180.0 if to_back else 0.0

        progress_anim = QPropertyAnimation(self, b"flipProgress")
        progress_anim.setDuration(320)
        progress_anim.setStartValue(start)
        progress_anim.setEndValue(end)
        progress_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        front_opacity = QPropertyAnimation(self._front_opacity, b"opacity")
        front_opacity.setDuration(320)
        front_opacity.setStartValue(1.0 if not to_back else 0.0)
        front_opacity.setEndValue(0.0 if to_back else 1.0)

        back_opacity = QPropertyAnimation(self._back_opacity, b"opacity")
        back_opacity.setDuration(320)
        back_opacity.setStartValue(0.0 if not to_back else 1.0)
        back_opacity.setEndValue(1.0 if to_back else 0.0)

        group = QParallelAnimationGroup(self)
        group.addAnimation(progress_anim)
        group.addAnimation(front_opacity)
        group.addAnimation(back_opacity)
        self._anim_group = group
        group.start()

    def get_flip_progress(self) -> float:
        return self._flip_progress

    def set_flip_progress(self, value: float) -> None:
        self._flip_progress = value
        scale = abs(1.0 - (value / 90.0)) if value <= 90 else abs((value - 90.0) / 90.0)
        scale = max(0.05, min(1.0, scale))
        transform_style = f"transform: scaleX({scale:.3f});"
        self.stack.setStyleSheet(f"QStackedWidget#flipTileStack {{ {transform_style} }}")

    flipProgress = Property(float, get_flip_progress, set_flip_progress)
