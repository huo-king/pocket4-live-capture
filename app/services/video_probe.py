"""ffprobe 读取视频信息"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.services.subprocess_util import run_text

from app.services.tool_paths import resolve_tool


@dataclass
class VideoInfo:
    path: str
    duration_sec: float
    width: int
    height: int
    codec: str
    fps: float
    has_audio: bool
    video_bitrate_bps: int = 0


# Qt 在 Windows 上常无法直接预览 HEVC/H.265，需生成 H.264 代理
HEVC_CODECS = frozenset({"hevc", "h265"})


def needs_preview_proxy(codec: str) -> bool:
    return (codec or "").lower() in HEVC_CODECS


def probe_video(video_path: str) -> VideoInfo:
    ffprobe = resolve_tool("ffprobe")
    cmd = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    result = run_text(cmd)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "ffprobe 执行失败"
        raise RuntimeError(stderr)

    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    duration_sec = float(fmt.get("duration", 0) or 0)

    video_stream = None
    has_audio = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        if stream.get("codec_type") == "audio":
            has_audio = True

    if video_stream is None:
        raise RuntimeError("未找到视频流")

    width = int(video_stream.get("width", 0) or 0)
    height = int(video_stream.get("height", 0) or 0)
    codec = video_stream.get("codec_name", "unknown") or "unknown"

    fps = 0.0
    rate = video_stream.get("r_frame_rate") or video_stream.get("avg_frame_rate")
    if rate and rate != "0/0":
        num, _, den = rate.partition("/")
        if den and float(den) != 0:
            fps = float(num) / float(den)

    video_bitrate_bps = _parse_bitrate(video_stream.get("bit_rate"))
    if video_bitrate_bps <= 0:
        video_bitrate_bps = _parse_bitrate(fmt.get("bit_rate"))

    return VideoInfo(
        path=video_path,
        duration_sec=duration_sec,
        width=width,
        height=height,
        codec=codec,
        fps=fps,
        has_audio=has_audio,
        video_bitrate_bps=video_bitrate_bps,
    )


def _parse_bitrate(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
