"""LUT 预览帧渲染 — 单次 FFmpeg 截帧+LUT，预览专用 rgb24。"""

from __future__ import annotations

from pathlib import Path

from app.services.lut_service import LutConfig, build_lut_vf
from app.services.photo_png_export import JPEG_TRANSIT_PIX_FMT
from app.services.subprocess_util import run_text
from app.services.tool_paths import resolve_tool
from app.services.video_probe import VideoInfo, probe_video

# 预览限幅：1280 边长 + rgb24，速度与清晰度平衡（导出仍全分辨率 rgb48le）
PREVIEW_MAX_EDGE = 1280
_SEEK_MARGIN_SEC = 2.0
_PREVIEW_SWS = "flags=lanczos+accurate_rnd+full_chroma_int"


def _preview_scale_filter(width: int, height: int) -> str | None:
    edge = max(width, height)
    if edge <= PREVIEW_MAX_EDGE:
        return None
    if width >= height:
        return f"scale={PREVIEW_MAX_EDGE}:-2:{_PREVIEW_SWS}"
    return f"scale=-2:{PREVIEW_MAX_EDGE}:{_PREVIEW_SWS}"


def render_lut_preview_frame(
    video_path: str,
    timestamp_sec: float,
    output_path: str,
    lut_config: LutConfig,
) -> None:
    """
    单次 FFmpeg：截帧 + LUT（可叠加）→ PNG。

    video_path 应与左侧播放器同源（含 H.264 代理），保证同帧对比。
    导出仍走原片全分辨率 rgb48le。
    """
    if not lut_config.active:
        raise ValueError("LUT 未启用，无法预览")

    ffmpeg = resolve_tool("ffmpeg")
    info = probe_video(video_path)
    coarse = max(0.0, timestamp_sec - _SEEK_MARGIN_SEC)
    fine = max(0.0, timestamp_sec - coarse)

    vf_parts: list[str] = []
    scale_vf = _preview_scale_filter(info.width, info.height)
    if scale_vf:
        vf_parts.append(scale_vf)
    vf_parts.append(build_lut_vf(lut_config))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{coarse:.6f}",
        "-i",
        video_path,
        "-ss",
        f"{fine:.6f}",
        "-vf",
        ",".join(vf_parts),
        "-frames:v",
        "1",
        "-update",
        "1",
        "-c:v",
        "png",
        "-compression_level",
        "3",
        "-pred",
        "mixed",
        "-pix_fmt",
        JPEG_TRANSIT_PIX_FMT,
        str(out),
    ]
    result = run_text(cmd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"LUT 预览失败: {detail}")

    if not out.is_file() or out.stat().st_size < 512:
        raise RuntimeError("LUT 预览生成失败")
