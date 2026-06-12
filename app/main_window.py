"""主窗口 — 页面路由与导出编排"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.capture_task import CaptureTask
from app.pages.batch_watermark_page import BatchWatermarkPage
from app.pages.live_preview_page import LivePreviewPage
from app.pages.player_page import PlayerPage
from app.services.batch_watermark_worker import BatchWatermarkWorker
from app.services.export_worker import (
    ExportWorker,
    build_motion_photo_filename,
    default_export_dir,
)
from app.services.preview_worker import PreviewFrameWorker
from app.services.quality_enhance_service import EnhanceMode
from app.services.proxy_preview_service import is_cache_valid, proxy_cache_path
from app.services.proxy_preview_worker import ProxyPreviewWorker
from app.services.video_probe import needs_preview_proxy, probe_video
from app.widgets.export_progress import ExportProgressDialog
from app.widgets.video_player import SUPPORTED_EXTENSIONS


class MainWindow(QMainWindow):
    PAGE_PLAYER = 0
    PAGE_LIVE_PREVIEW = 1
    PAGE_BATCH_WATERMARK = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pocket实况截图")
        self.resize(900, 900)
        self.setMinimumSize(400, 560)
        self.setAcceptDrops(True)

        self._video_path: str | None = None
        self._pending_timestamp_ms = 0
        self._last_loaded_video: str | None = None
        self._export_worker: ExportWorker | None = None
        self._preview_worker: PreviewFrameWorker | None = None
        self._batch_worker: BatchWatermarkWorker | None = None
        self._proxy_worker: ProxyPreviewWorker | None = None
        self._preview_path: str | None = None
        self._using_proxy_preview = False
        self._progress_dialog: ExportProgressDialog | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.player_page = PlayerPage()
        self.live_preview_page = LivePreviewPage()
        self.batch_watermark_page = BatchWatermarkPage()
        self.stack.addWidget(self.player_page)
        self.stack.addWidget(self.live_preview_page)
        self.stack.addWidget(self.batch_watermark_page)
        root.addWidget(self.stack)

        self.player_page.png_photo_clicked.connect(self._export_png_photo_at)
        self.player_page.jpeg_photo_clicked.connect(self._export_jpeg_photo_at)
        self.player_page.live_clicked.connect(self._go_live_preview_at)
        self.player_page.batch_watermark_clicked.connect(self._go_batch_watermark)
        self.player_page.video_error.connect(self._show_error)
        self.player_page.video_dropped.connect(self._load_video)

        self.live_preview_page.back_clicked.connect(self._back_to_player)
        self.live_preview_page.export_clicked.connect(self._export_motion_photo)
        self.live_preview_page.video_dropped.connect(self._load_video)

        self.batch_watermark_page.back_clicked.connect(self._back_to_player)
        self.batch_watermark_page.pick_output_dir.connect(self._pick_batch_output_dir)
        self.batch_watermark_page.pick_files.connect(self._pick_batch_files)
        self.batch_watermark_page.start_batch.connect(self._start_batch_watermark)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self._accepts_video_drop(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        path = self._first_video_path(event.mimeData())
        if path:
            self._load_video(path)
        event.acceptProposedAction()

    def _accepts_video_drop(self, mime) -> bool:
        if not mime.hasUrls():
            return False
        for url in mime.urls():
            ext = Path(url.toLocalFile()).suffix
            if ext in SUPPORTED_EXTENSIONS:
                return True
        return False

    def _first_video_path(self, mime) -> str | None:
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            path = url.toLocalFile()
            if Path(path).suffix in SUPPORTED_EXTENSIONS:
                return path
        return None

    def _load_video(self, path: str) -> None:
        resolved = str(Path(path).resolve())

        self._cleanup_preview_worker()
        self._cancel_proxy_worker()
        if self._progress_dialog:
            self._progress_dialog.reject()
            self._progress_dialog = None

        self._video_path = resolved
        self._preview_path = None
        self._using_proxy_preview = False
        self.stack.setCurrentIndex(self.PAGE_PLAYER)

        try:
            info = probe_video(resolved)
        except RuntimeError as exc:
            self.player_page.show_load_error(str(exc))
            return

        if not needs_preview_proxy(info.codec):
            self._preview_path = resolved
            self._last_loaded_video = resolved
            self.player_page.load_video(resolved)
            print(f"[INFO] 收到视频文件: {resolved} ({info.codec})")
            return

        cache = proxy_cache_path(resolved)
        if is_cache_valid(cache, Path(resolved)):
            self._preview_path = str(cache)
            self._using_proxy_preview = True
            hint = (
                f"预览为 H.264 代理（原片 {info.codec.upper()}）；"
                "截帧/导出仍用原片，不影响画质"
            )
            self._last_loaded_video = resolved
            self.player_page.load_video(str(cache), hint=hint)
            print(f"[INFO] 使用缓存预览代理: {cache}")
            return

        self.player_page.show_loading_message("HEVC 原片正在生成 H.264 预览代理…")

        self._progress_dialog = ExportProgressDialog(self)
        self._progress_dialog.setWindowTitle("预览代理")
        self._progress_dialog.show()

        self._proxy_worker = ProxyPreviewWorker(resolved, parent=self)
        self._proxy_worker.progress.connect(self._on_export_progress)
        self._proxy_worker.finished_ok.connect(self._on_proxy_ready)
        self._proxy_worker.failed.connect(self._on_proxy_failed)
        self._proxy_worker.finished.connect(self._on_proxy_finished)
        self._proxy_worker.start()
        print(f"[INFO] 生成 HEVC 预览代理: {resolved}")

    def _cancel_proxy_worker(self) -> None:
        if self._proxy_worker is None:
            return
        worker = self._proxy_worker
        self._proxy_worker = None
        for signal in (worker.progress, worker.finished_ok, worker.failed, worker.finished):
            try:
                signal.disconnect()
            except (RuntimeError, TypeError):
                pass
        if worker.isRunning():
            worker.wait(5000)

    def _on_proxy_ready(self, preview_path: str, using_proxy: bool) -> None:
        if self.sender() is not self._proxy_worker:
            return
        if self._progress_dialog:
            self._progress_dialog.accept()
        self._preview_path = preview_path
        self._using_proxy_preview = using_proxy
        hint = None
        if using_proxy:
            hint = "预览为 H.264 代理；截帧/导出仍用原片，不影响画质"
        if self._video_path:
            self._last_loaded_video = self._video_path
        self.player_page.load_video(preview_path, hint=hint)

    def _on_proxy_failed(self, message: str) -> None:
        if self.sender() is not self._proxy_worker:
            return
        if self._progress_dialog:
            self._progress_dialog.reject()
        self._show_error(
            f"{message}\n\n可尝试安装 Microsoft Store 的「HEVC 视频扩展」，"
            "或确认 tools/ffmpeg 可用。"
        )
        if self._video_path:
            self._preview_path = self._video_path
            self.player_page.load_video(
                self._video_path,
                hint="预览代理失败，尝试直接加载原片…",
            )

    def _on_proxy_finished(self) -> None:
        self._proxy_worker = None
        self._progress_dialog = None

    def _playback_video_path(self) -> str | None:
        return self._preview_path or self._video_path

    def _export_png_photo_at(self, timestamp_ms: int) -> None:
        if not self._video_path:
            return
        self._pending_timestamp_ms = timestamp_ms
        self._export_png_photo()

    def _export_jpeg_photo_at(self, timestamp_ms: int) -> None:
        if not self._video_path:
            return
        self._pending_timestamp_ms = timestamp_ms
        self._export_jpeg_photo()

    def _go_live_preview_at(self, timestamp_ms: int) -> None:
        if not self._video_path:
            return
        self._pending_timestamp_ms = timestamp_ms
        self._go_live_preview()

    def _build_task(self, timestamp_ms: int) -> CaptureTask:
        duration_ms = self.player_page.video_player.duration_ms
        task = CaptureTask(
            video_path=self._video_path or "",
            timestamp_ms=timestamp_ms,
        )
        task.compute_clip_bounds(max(duration_ms / 1000.0, 0.0))
        return task

    def _go_live_preview(self) -> None:
        self._cleanup_preview_worker()

        task = CaptureTask(
            video_path=self._video_path or "",
            timestamp_ms=self._pending_timestamp_ms,
        )
        use_video_preview = not self.player_page.is_watermark_enabled()
        self.live_preview_page.show_loading(
            task,
            use_video_preview=use_video_preview,
            preview_video_path=self._playback_video_path(),
            apply_watermark=self.player_page.is_watermark_enabled(),
            apply_enhance=self.player_page.get_enhance_mode() != EnhanceMode.OFF,
            enhance_mode=self.player_page.get_enhance_mode(),
        )
        self.stack.setCurrentIndex(self.PAGE_LIVE_PREVIEW)

        if use_video_preview:
            return

        self._preview_worker = PreviewFrameWorker(
            task,
            apply_watermark=self.player_page.is_watermark_enabled(),
            parent=self,
        )
        self._preview_worker.finished_ok.connect(self._on_preview_ready)
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.finished.connect(self._on_preview_worker_finished)
        self._preview_worker.start()

    def _on_preview_ready(self, task: CaptureTask, frame_path: str) -> None:
        self.live_preview_page.set_preview_from_file(task, frame_path)
        if self._preview_worker is not None:
            self._preview_worker.cleanup()

    def _on_preview_failed(self, message: str) -> None:
        self.live_preview_page.set_preview_failed(message)

    def _on_preview_worker_finished(self) -> None:
        self._preview_worker = None

    def _cleanup_preview_worker(self) -> None:
        if self._preview_worker is None:
            return
        if self._preview_worker.isRunning():
            self._preview_worker.wait(3000)
        self._preview_worker.cleanup()
        self._preview_worker = None

    def _back_to_player(self) -> None:
        self._cleanup_preview_worker()
        self.stack.setCurrentIndex(self.PAGE_PLAYER)

    def _go_batch_watermark(self) -> None:
        self.stack.setCurrentIndex(self.PAGE_BATCH_WATERMARK)

    def _pick_batch_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择批量输出目录",
            self.batch_watermark_page.output_dir,
        )
        if folder:
            self.batch_watermark_page.set_output_dir(folder)

    def _pick_batch_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择照片 / 实况图",
            str(Path.home() / "Pictures"),
            "图片与实况 (*.png *.jpg *.jpeg);;所有文件 (*.*)",
        )
        if paths:
            self.batch_watermark_page.add_files(paths)

    def _start_batch_watermark(self, paths: list[str], output_dir: str) -> None:
        if self._batch_worker and self._batch_worker.isRunning():
            return

        self.batch_watermark_page.set_busy(True)
        self._progress_dialog = ExportProgressDialog(self)
        self._progress_dialog.setWindowTitle("批量加水印")
        self._progress_dialog.show()

        self._batch_worker = BatchWatermarkWorker(paths, output_dir, parent=self)
        self._batch_worker.progress.connect(self._on_export_progress)
        self._batch_worker.finished_ok.connect(self._on_batch_success)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.finished.connect(self._on_batch_finished)
        self._batch_worker.start()

    def _on_batch_success(self, results: list) -> None:
        if self._progress_dialog:
            self._progress_dialog.accept()
        notes = [r.note for r in results]
        last_output = results[-1].output_path if results else ""
        summary = f"共处理 {len(results)} 个文件"
        self._show_success_dialog(
            last_output,
            [summary, *notes[:5]],
            title="批量加水印完成",
        )

    def _on_batch_failed(self, message: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.reject()
        self._show_error(message)

    def _on_batch_finished(self) -> None:
        self.batch_watermark_page.set_busy(False)
        self._batch_worker = None
        self._progress_dialog = None

    def _export_png_photo(self) -> None:
        if not self._video_path:
            return
        task = self._build_task(self._pending_timestamp_ms)
        stem = Path(self._video_path).stem
        default_name = f"{stem}_{task.timestamp_ms}ms.png"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 PNG 无损照片",
            str(Path(default_export_dir()) / default_name),
            "PNG 无损 (*.png)",
        )
        if not save_path:
            return
        if not save_path.lower().endswith(".png"):
            save_path = str(Path(save_path).with_suffix(".png"))
        self._start_export(task, save_path, ExportWorker.MODE_PHOTO_PNG)

    def _export_jpeg_photo(self) -> None:
        if not self._video_path:
            return
        task = self._build_task(self._pending_timestamp_ms)
        stem = Path(self._video_path).stem
        default_name = f"{stem}_{task.timestamp_ms}ms.jpg"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 JPEG 最高质量照片",
            str(Path(default_export_dir()) / default_name),
            "JPEG 最高质量 (*.jpg *.jpeg)",
        )
        if not save_path:
            return
        if Path(save_path).suffix.lower() not in (".jpg", ".jpeg"):
            save_path = str(Path(save_path).with_suffix(".jpg"))
        self._start_export(task, save_path, ExportWorker.MODE_PHOTO_JPEG)

    def _export_motion_photo(self, task: CaptureTask) -> None:
        if self.live_preview_page.export_btn.isEnabled() is False:
            return

        default_name = build_motion_photo_filename(task.video_path, task.timestamp_ms)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Motion Photo",
            str(Path(default_export_dir()) / default_name),
            "Motion Photo (*.jpg)",
        )
        if not save_path:
            return
        if not Path(save_path).name.startswith("MV"):
            save_path = str(Path(save_path).with_name(f"MVIMG_{Path(save_path).name}"))
        self._start_export(task, save_path, ExportWorker.MODE_MOTION)

    def _start_export(self, task: CaptureTask, output_path: str, mode: str) -> None:
        if self._export_worker and self._export_worker.isRunning():
            return

        self.live_preview_page.export_btn.setEnabled(False)
        self._progress_dialog = ExportProgressDialog(self)
        self._progress_dialog.show()

        self._export_worker = ExportWorker(
            task,
            output_path,
            mode=mode,
            apply_watermark=self.player_page.is_watermark_enabled(),
            enhance_mode=self.player_page.get_enhance_mode(),
            parent=self,
        )
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished_ok.connect(self._on_export_success)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.start()

    def _on_export_progress(self, value: int, message: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.update_progress(value, message)

    def _on_export_success(self, output_path: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.accept()
        quality_notes: list[str] = []
        if self._export_worker:
            if self._export_worker.last_frame_note:
                quality_notes.append(self._export_worker.last_frame_note)
            if self._export_worker.last_clip_quality:
                quality_notes.append(f"视频：{self._export_worker.last_clip_quality}")
        self._show_success_dialog(output_path, quality_notes)

    def _on_export_failed(self, message: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.reject()
        self._show_error(message)

    def _on_export_finished(self) -> None:
        self.live_preview_page.export_btn.setEnabled(True)
        self._export_worker = None
        self._progress_dialog = None

    def _show_success_dialog(
        self,
        output_path: str,
        quality_notes: list[str] | None = None,
        *,
        title: str | None = None,
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("导出成功")
        dialog.setMinimumWidth(420)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        if title:
            dialog_title = title
        elif Path(output_path).name.startswith("MV"):
            dialog_title = "Motion Photo 已导出"
        else:
            dialog_title = "照片已导出"

        title_label = QLabel(dialog_title)

        path_label = QLabel(output_path)
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #B0B0B0;")
        layout.addWidget(path_label)

        if quality_notes:
            quality_label = QLabel("\n".join(quality_notes))
            quality_label.setWordWrap(True)
            quality_label.setStyleSheet("color: #4DA3FF; font-size: 12px;")
            layout.addWidget(quality_label)

        if Path(output_path).name.startswith("MV"):
            tip = QLabel(
                "传到手机：请用 USB 复制到 DCIM 文件夹，不要用微信/QQ。\n"
                "红米/MIUI 若相册无动态效果，请安装 Google 相册查看，"
                "或升级至 HyperOS 后使用系统相册。"
            )
            tip.setWordWrap(True)
            tip.setStyleSheet("color: #888888; font-size: 12px;")
            layout.addWidget(tip)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("打开所在文件夹")
        open_btn.clicked.connect(lambda: self._open_folder(output_path))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    @staticmethod
    def _open_folder(file_path: str) -> None:
        folder = str(Path(file_path).resolve().parent)
        if os.name == "nt":
            subprocess.run(["explorer", "/select,", os.path.normpath(file_path)], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "错误", message)
