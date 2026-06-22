"""后台导出线程 — Motion Photo / 静帧照片"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.models.capture_task import CaptureTask
from app.services.ffmpeg_service import FFmpegService
from app.services.motion_photo_service import MotionPhotoService
from app.services.photo_jpeg_export import export_photo_jpeg
from app.services.photo_png_export import export_photo_png
from app.services.export_naming import build_motion_photo_filename, default_export_dir
from app.services.lut_motion_export import (
    apply_lut_to_motion_clip,
    should_apply_lut_to_motion_video,
)
from app.services.lut_service import LUT_DISABLED, LutConfig
from app.services.quality_enhance_service import EnhanceMode, enhance_video_clip, should_enhance_motion_video


class ExportWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str)
    failed = Signal(str)

    MODE_MOTION = "motion"
    MODE_PHOTO_PNG = "photo_png"
    MODE_PHOTO_JPEG = "photo_jpeg"

    def __init__(
        self,
        task: CaptureTask,
        output_path: str,
        mode: str = MODE_MOTION,
        *,
        apply_watermark: bool = False,
        enhance_mode: EnhanceMode = EnhanceMode.OFF,
        lut_config: LutConfig = LUT_DISABLED,
        parent=None,
    ):
        super().__init__(parent)
        self.task = task
        self.output_path = output_path
        self.mode = mode
        self.apply_watermark = apply_watermark
        self.enhance_mode = enhance_mode
        self.lut_config = lut_config
        self._ffmpeg = FFmpegService()
        self._motion = MotionPhotoService()
        self.last_frame_note: str = ""
        self.last_clip_quality: str = ""

    def _emit_progress(self, value: int, message: str) -> None:
        self.progress.emit(value, message)

    def run(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"pocket_live_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            if self.mode == self.MODE_PHOTO_PNG:
                self.progress.emit(5, "PNG 无损截帧…")
                note = export_photo_png(
                    self.task.video_path,
                    self.task.timestamp_sec,
                    self.output_path,
                    apply_watermark=self.apply_watermark,
                    enhance_mode=self.enhance_mode,
                    lut_config=self.lut_config,
                    on_progress=self._emit_progress,
                )
                self.last_frame_note = note
                self.progress.emit(100, "完成")
                self.finished_ok.emit(self.output_path)
                return

            if self.mode == self.MODE_PHOTO_JPEG:
                self.progress.emit(5, "PNG 无损截帧…")
                note = export_photo_jpeg(
                    self.task.video_path,
                    self.task.timestamp_sec,
                    self.output_path,
                    apply_watermark=self.apply_watermark,
                    enhance_mode=self.enhance_mode,
                    lut_config=self.lut_config,
                    on_progress=self._emit_progress,
                )
                self.last_frame_note = note
                self.progress.emit(100, "完成")
                self.finished_ok.emit(self.output_path)
                return

            self.progress.emit(5, "读取视频信息…")
            info = self._ffmpeg.probe(self.task.video_path)
            self.task.compute_clip_bounds(info.duration_sec)

            frame_path = str(temp_dir / "frame.jpg")

            self.progress.emit(20, "生成实况封面…")
            enhance_note = self._ffmpeg.extract_frame(
                self.task.video_path,
                self.task.timestamp_sec,
                frame_path,
                apply_watermark=self.apply_watermark,
                enhance_mode=self.enhance_mode,
                lut_config=self.lut_config,
                video_info=info,
            )
            frame_mb = Path(frame_path).stat().st_size / (1024 * 1024)
            if self.enhance_mode != EnhanceMode.OFF or self.lut_config.active:
                self.last_frame_note = (
                    f"封面：{enhance_note or '已处理'} → JPEG(100/4:4:4) · {frame_mb:.1f} MB"
                )
            else:
                self.last_frame_note = (
                    f"封面：PNG 无损 → JPEG(100/4:4:4) · {frame_mb:.1f} MB"
                )
            if self.apply_watermark:
                self.last_frame_note += " · 已加水印"

            clip_path = str(temp_dir / "clip.mp4")
            self.progress.emit(40, "裁切实况视频片段…")
            clip_result = self._ffmpeg.extract_clip(
                self.task.video_path,
                self.task.clip_start_sec,
                self.task.clip_duration_sec,
                clip_path,
                has_audio=info.has_audio,
                for_motion_photo=True,
            )

            if should_apply_lut_to_motion_video(self.lut_config, self.enhance_mode):
                lut_out = str(temp_dir / "clip_lut.mp4")
                clip_path, lut_note = apply_lut_to_motion_clip(
                    clip_path,
                    lut_out,
                    self.lut_config,
                    self.enhance_mode,
                    on_progress=self._emit_progress,
                )
                if lut_note:
                    self.last_clip_quality = lut_note
            elif self.enhance_mode != EnhanceMode.OFF and should_enhance_motion_video(
                self.enhance_mode
            ):
                enhanced_clip = str(temp_dir / "clip_enhanced.mp4")
                self.progress.emit(50, "AI 增强实况视频（请耐心等待）…")

                def on_clip_progress(value: int, message: str) -> None:
                    mapped = 50 + int(value * 0.35)
                    self.progress.emit(mapped, message)

                video_result = enhance_video_clip(
                    clip_path,
                    enhanced_clip,
                    mode=self.enhance_mode,
                    on_progress=on_clip_progress,
                )
                clip_path = enhanced_clip
                self.last_clip_quality = video_result.note
            else:
                self.last_clip_quality = clip_result.quality_label
                if self.enhance_mode != EnhanceMode.OFF:
                    self.last_clip_quality += " · 内嵌视频保持原画 stream copy"
                if self.lut_config.active and not should_apply_lut_to_motion_video(
                    self.lut_config, self.enhance_mode
                ):
                    self.last_clip_quality += " · 内嵌视频原画（LUT 仅封面）"

            if Path(clip_path).stat().st_size <= 0:
                raise RuntimeError("视频片段裁切失败：输出文件为空")

            self.progress.emit(88, "封装 Motion Photo…")
            self._motion.create(
                frame_path,
                clip_path,
                self.output_path,
                self.task.presentation_us,
            )

            self.progress.emit(100, "完成")
            total_mb = Path(self.output_path).stat().st_size / (1024 * 1024)
            self.last_clip_quality += f" · 合计 {total_mb:.1f} MB"
            self.finished_ok.emit(self.output_path)
        except Exception as exc:
            self.failed.emit(_friendly_error(str(exc)))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


__all__ = ["ExportWorker", "build_motion_photo_filename", "default_export_dir"]


def _friendly_error(message: str) -> str:
    text = message.strip()
    if "未找到 ffmpeg" in text or "ffmpeg" in text.lower() and "not found" in text.lower():
        return "未找到 FFmpeg，请将 ffmpeg.exe 放到 tools/ 目录或安装到系统 PATH"
    if "Real-ESRGAN" in text or "realesrgan" in text.lower():
        return text
    if "未找到 ffprobe" in text:
        return "未找到 ffprobe，请将 ffprobe.exe 放到 tools/ 目录"
    if "未找到 exiftool" in text:
        return "未找到 ExifTool，请将 exiftool.exe 放到 tools/ 目录"
    if "No space left" in text:
        return "磁盘空间不足，请清理后重试"
    return text or "导出失败，请重试"
