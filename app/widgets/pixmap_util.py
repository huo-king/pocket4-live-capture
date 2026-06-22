"""高 DPI 友好的 Pixmap 缩放 — 预览窗清晰显示。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget


def fit_pixmap_to_widget(pixmap: QPixmap, widget: QWidget) -> QPixmap:
    """按控件逻辑尺寸 × 设备像素比缩放，避免预览发糊。"""
    if pixmap.isNull() or widget.width() <= 0 or widget.height() <= 0:
        return QPixmap()

    dpr = widget.devicePixelRatioF()
    label_w = max(1, int(widget.width() * dpr))
    label_h = max(1, int(widget.height() * dpr))

    src_w = pixmap.width()
    src_h = pixmap.height()
    if src_w <= 0 or src_h <= 0:
        return QPixmap()

    scale = min(label_w / src_w, label_h / src_h, 1.0)
    target_w = max(1, int(src_w * scale))
    target_h = max(1, int(src_h * scale))

    if scale >= 1.0:
        result = QPixmap(pixmap)
    else:
        image = pixmap.toImage().scaled(
            QSize(target_w, target_h),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        result = QPixmap.fromImage(image)

    result.setDevicePixelRatio(dpr)
    return result
