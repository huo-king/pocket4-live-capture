"""批量加水印后台线程"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services.batch_watermark_service import (
    BatchWatermarkResult,
    collect_supported_files,
    default_batch_output_path,
    watermark_file,
)


class BatchWatermarkWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        input_paths: list[str],
        output_dir: str,
        parent=None,
    ):
        super().__init__(parent)
        self.input_paths = input_paths
        self.output_dir = output_dir
        self.results: list[BatchWatermarkResult] = []

    def run(self) -> None:
        try:
            paths = collect_supported_files(self.input_paths)
            if not paths:
                raise ValueError("没有可处理的 PNG / JPEG / 实况图文件")

            total = len(paths)
            out_dir = Path(self.output_dir)
            self.results = []

            for index, src_path in enumerate(paths, start=1):
                name = src_path.name
                pct = int((index - 1) / total * 100)
                self.progress.emit(pct, f"处理 {index}/{total}: {name}")

                dst = default_batch_output_path(src_path, out_dir)
                result = watermark_file(src_path, dst)
                self.results.append(result)

            self.progress.emit(100, "完成")
            self.finished_ok.emit(self.results)
        except Exception as exc:
            self.failed.emit(str(exc).strip() or "批量加水印失败")
