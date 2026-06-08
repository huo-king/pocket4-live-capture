"""HEVC 预览代理后台线程"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services.proxy_preview_service import (
    generate_proxy,
    is_cache_valid,
    proxy_cache_path,
)
from app.services.video_probe import needs_preview_proxy, probe_video


class ProxyPreviewWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str, bool)  # preview_path, using_proxy
    failed = Signal(str)

    def __init__(self, source_path: str, parent=None):
        super().__init__(parent)
        self.source_path = source_path

    def run(self) -> None:
        try:
            src = Path(self.source_path)
            info = probe_video(str(src))
            if not needs_preview_proxy(info.codec):
                self.progress.emit(100, "原片可直接预览")
                self.finished_ok.emit(str(src.resolve()), False)
                return

            cache = proxy_cache_path(src)
            if is_cache_valid(cache, src):
                self.progress.emit(100, "使用已缓存的预览代理")
                self.finished_ok.emit(str(cache), True)
                return

            self.progress.emit(10, "HEVC 原片 Windows 无法直接预览，正在生成 H.264 代理…")

            def on_progress(value: int, message: str) -> None:
                self.progress.emit(value, message)

            preview = generate_proxy(src, cache, on_progress=on_progress)
            self.finished_ok.emit(preview, True)
        except Exception as exc:
            self.failed.emit(str(exc).strip() or "预览代理生成失败")
