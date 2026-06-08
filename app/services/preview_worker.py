"""后台截取封面预览帧 — PNG 无损，避免 JPEG 预览发糊"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.models.capture_task import CaptureTask
from app.services.ffmpeg_service import FFmpegService
from app.services.photo_png_export import export_preview_png


class PreviewFrameWorker(QThread):
    finished_ok = Signal(object, str)
    failed = Signal(str)

    def __init__(
        self, task: CaptureTask, *, apply_watermark: bool = False, parent=None
    ):
        super().__init__(parent)
        self.task = task
        self.apply_watermark = apply_watermark
        self._ffmpeg = FFmpegService()
        self._temp_dir: Path | None = None

    def run(self) -> None:
        self._temp_dir = Path(tempfile.gettempdir()) / f"pocket_preview_{uuid.uuid4().hex}"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            info = self._ffmpeg.probe(self.task.video_path)
            self.task.compute_clip_bounds(info.duration_sec)

            frame_path = str(self._temp_dir / "preview.png")
            export_preview_png(
                self.task.video_path,
                self.task.timestamp_sec,
                frame_path,
                apply_watermark=self.apply_watermark,
            )

            if not Path(frame_path).is_file() or Path(frame_path).stat().st_size == 0:
                raise RuntimeError("封面帧生成失败，请检查视频文件是否完整")

            self.finished_ok.emit(self.task, frame_path)
        except Exception as exc:
            self.cleanup()
            msg = str(exc).strip() or "封面预览失败"
            if "未找到 ffmpeg" in msg:
                msg = "未找到 FFmpeg，请将 ffmpeg.exe 放到 tools/ 目录"
            self.failed.emit(msg)

    def cleanup(self) -> None:
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
