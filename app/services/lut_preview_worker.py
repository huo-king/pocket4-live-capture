"""后台生成 LUT 预览帧 — 不阻塞 UI。"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services.lut_preview_render import render_lut_preview_frame
from app.services.lut_service import LUT_DISABLED, LutConfig


class LutPreviewWorker(QThread):
    finished_ok = Signal(str, int, int)
    failed = Signal(str)

    def __init__(
        self,
        video_path: str,
        timestamp_ms: int,
        lut_config: LutConfig,
        *,
        parent=None,
    ):
        super().__init__(parent)
        self.video_path = video_path
        self.timestamp_ms = timestamp_ms
        self.lut_config = lut_config
        self._temp_dir: Path | None = None
        self._generation = 0

    def set_generation(self, generation: int) -> None:
        self._generation = generation

    def run(self) -> None:
        if not self.lut_config.active:
            self.failed.emit("LUT 未启用")
            return

        generation = self._generation
        self._temp_dir = Path(tempfile.gettempdir()) / f"pocket_lut_preview_{uuid.uuid4().hex}"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(self._temp_dir / "lut_preview.png")

        try:
            render_lut_preview_frame(
                self.video_path,
                self.timestamp_ms / 1000.0,
                out_path,
                self.lut_config,
            )
            if generation != self._generation:
                return
            if not Path(out_path).is_file():
                raise RuntimeError("预览文件为空")
            self.finished_ok.emit(out_path, self.timestamp_ms, generation)
        except Exception as exc:
            if generation == self._generation:
                self.failed.emit(str(exc).strip() or "LUT 预览失败")

    def cleanup(self) -> None:
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
