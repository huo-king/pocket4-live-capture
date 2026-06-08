"""FFmpeg 裁切（实况视频 stream copy）+ 实况封面委托 JPEG 导出模块"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.services.photo_jpeg_export import export_motion_cover_jpeg
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
    ) -> None:
        """实况封面：PNG 无损截帧 → 最高质量 JPEG（与照片 JPEG 同链路）。"""
        export_motion_cover_jpeg(
            video_path,
            timestamp_sec,
            output_jpg,
            apply_watermark=apply_watermark,
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
        self._stream_copy(video_path, start_sec, duration_sec, output_mp4, has_audio)

        clip_path = Path(output_mp4)
        if not self._validate_clip(
            output_mp4,
            duration_sec,
            source_info=source_info,
        ):
            clip_path.unlink(missing_ok=True)
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
    ) -> None:
        """-ss 放在 -i 之后，精确裁切；stream copy 保持原片码率。"""
        ffmpeg = resolve_tool("ffmpeg")
        end_sec = start_sec + duration_sec
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            video_path,
            "-ss",
            f"{start_sec:.6f}",
            "-to",
            f"{end_sec:.6f}",
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
            # 时长必须接近预期（3s 片段允许 ±0.25s）
            tolerance = max(0.25, expected_duration * 0.08)
            if abs(info.duration_sec - expected_duration) > tolerance:
                return False

            # 体积不得低于原片码率估算的 60%（防止裁切到空壳/残段）
            if source_info and source_info.video_bitrate_bps > 0:
                expected_bytes = (
                    source_info.video_bitrate_bps * expected_duration / 8
                )
                if clip_bytes < expected_bytes * 0.6:
                    return False

        return True

    @staticmethod
    def _run(cmd: list[str], error_prefix: str) -> None:
        result = run_text(cmd)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"{error_prefix}: {detail}")
