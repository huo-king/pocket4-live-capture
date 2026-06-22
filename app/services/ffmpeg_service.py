"""FFmpeg 裁切（实况视频 stream copy）+ 实况封面委托 JPEG 导出模块"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.services.lut_service import LUT_DISABLED, LutConfig
from app.services.photo_jpeg_export import export_motion_cover_jpeg
from app.services.photo_png_export import transit_pix_fmt_for_export
from app.services.quality_enhance_service import EnhanceMode
from app.services.subprocess_util import run_text
from app.services.tool_paths import resolve_tool
from app.services.video_probe import VideoInfo, probe_video


class ClipExtractMode(str, Enum):
    COPY = "copy"


@dataclass
class ClipExtractResult:
    path: str
    mode: ClipExtractMode
    codec: str
    clip_size_bytes: int = 0
    clip_duration_sec: float = 0.0

    @property
    def quality_label(self) -> str:
        mb = self.clip_size_bytes / (1024 * 1024)
        return (
            f"原画裁切（stream copy，零重编码）· {self.codec} · "
            f"{mb:.1f} MB · {self.clip_duration_sec:.1f}s"
        )


class FFmpegService:
    def probe(self, video_path: str) -> VideoInfo:
        return probe_video(video_path)

    def extract_frame(
        self,
        video_path: str,
        timestamp_sec: float,
        output_jpg: str,
        *,
        apply_watermark: bool = False,
        enhance_mode: EnhanceMode = EnhanceMode.OFF,
        lut_config: LutConfig = LUT_DISABLED,
        video_info: VideoInfo | None = None,
    ) -> str | None:
        """实况封面：PNG 无损截帧 → [LUT] → [增强] → 最高质量 JPEG。"""
        return export_motion_cover_jpeg(
            video_path,
            timestamp_sec,
            output_jpg,
            apply_watermark=apply_watermark,
            enhance_mode=enhance_mode,
            lut_config=lut_config,
            video_info=video_info,
        )

    def extract_clip(
        self,
        video_path: str,
        start_sec: float,
        duration_sec: float,
        output_mp4: str,
        has_audio: bool = True,
        *,
        for_motion_photo: bool = False,
    ) -> ClipExtractResult:
        if for_motion_photo:
            return self._extract_clip_lossless_copy(
                video_path, start_sec, duration_sec, output_mp4, has_audio
            )

        self._stream_copy(video_path, start_sec, duration_sec, output_mp4, has_audio)
        info = probe_video(output_mp4)
        return ClipExtractResult(
            output_mp4,
            ClipExtractMode.COPY,
            info.codec,
            clip_size_bytes=Path(output_mp4).stat().st_size,
            clip_duration_sec=info.duration_sec,
        )

    def _extract_clip_lossless_copy(
        self,
        video_path: str,
        start_sec: float,
        duration_sec: float,
        output_mp4: str,
        has_audio: bool,
    ) -> ClipExtractResult:
        """实况片段：仅 stream copy，绝不重编码 / remux"""
        source_info = probe_video(video_path)
        clip_path = Path(output_mp4)

        # 先走快速关键帧裁切；校验失败再精确裁切（仍 stream copy，仅更慢）
        for accurate in (False, True):
            self._stream_copy(
                video_path,
                start_sec,
                duration_sec,
                output_mp4,
                has_audio,
                accurate=accurate,
            )
            if self._validate_clip(
                output_mp4,
                duration_sec,
                source_info=source_info,
                keyframe_aligned=not accurate,
            ):
                break
            clip_path.unlink(missing_ok=True)
        else:
            raise RuntimeError(
                "无法无损裁切此位置的视频片段（时长不足或非关键帧对齐）。"
                "请拖动时间轴到稍早/稍晚位置再导出，或换一段视频重试。"
            )

        info = probe_video(output_mp4)
        return ClipExtractResult(
            output_mp4,
            ClipExtractMode.COPY,
            info.codec,
            clip_size_bytes=clip_path.stat().st_size,
            clip_duration_sec=info.duration_sec,
        )

    def _stream_copy(
        self,
        video_path: str,
        start_sec: float,
        duration_sec: float,
        output_mp4: str,
        has_audio: bool,
        *,
        accurate: bool = False,
    ) -> None:
        """
        stream copy 裁切，保持原片码率。

        fast：-ss 在 -i 前，对齐关键帧，速度快。
        accurate：-ss 在 -i 后，边界更准，长视频较慢。
        """
        ffmpeg = resolve_tool("ffmpeg")
        if accurate:
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                video_path,
                "-ss",
                f"{start_sec:.6f}",
                "-t",
                f"{duration_sec:.6f}",
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                output_mp4,
            ]
        else:
            cmd = [
                ffmpeg,
                "-y",
                "-ss",
                f"{start_sec:.6f}",
                "-i",
                video_path,
                "-t",
                f"{duration_sec:.6f}",
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                output_mp4,
            ]
        if not has_audio:
            cmd.insert(-1, "-an")
        self._run(cmd, "视频无损裁切失败")

    @staticmethod
    def _validate_clip(
        clip_path: str,
        expected_duration: float,
        *,
        source_info: VideoInfo | None = None,
        keyframe_aligned: bool = False,
    ) -> bool:
        path = Path(clip_path)
        if not path.is_file() or path.stat().st_size < 1024:
            return False

        data = path.read_bytes()
        if b"ftyp" not in data[:4096]:
            return False

        try:
            info = probe_video(clip_path)
        except RuntimeError:
            return False

        if info.duration_sec <= 0.1:
            return False

        clip_bytes = path.stat().st_size

        if expected_duration > 0:
            # 快速关键帧裁切允许更大偏差；精确裁切仍用较紧阈值
            if keyframe_aligned:
                tolerance = max(0.5, expected_duration * 0.2)
                min_duration = max(1.5, expected_duration * 0.5)
                min_bitrate_ratio = 0.45
            else:
                tolerance = max(0.25, expected_duration * 0.08)
                min_duration = expected_duration * 0.85
                min_bitrate_ratio = 0.6

            if info.duration_sec < min_duration:
                return False
            if abs(info.duration_sec - expected_duration) > tolerance:
                return False

            if source_info and source_info.video_bitrate_bps > 0:
                expected_bytes = (
                    source_info.video_bitrate_bps * expected_duration / 8
                )
                if clip_bytes < expected_bytes * min_bitrate_ratio:
                    return False

        return True

    @staticmethod
    def _run(cmd: list[str], error_prefix: str) -> None:
        result = run_text(cmd)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"{error_prefix}: {detail}")
