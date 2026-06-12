"""PNG 无损照片导出 — 独立模块，与 JPEG 导出分离"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.services.photo_watermark import apply_watermark_to_png_file
from app.services.quality_enhance_service import (
    EnhanceMode,
    ProgressCallback,
    enhance_png_file,
    is_realesrgan_mode,
)
from app.services.subprocess_util import run_text
from app.services.tool_paths import resolve_tool
from app.services.video_probe import VideoInfo, probe_video

# 两阶段 seek：先在 -i 前粗定位，再只解码末尾一小段，避免从 0 秒扫到 80+ 秒
_SEEK_MARGIN_SEC = 2.0
PNG_LOSSLESS_PIX_FMT = "rgb48le"
# JPEG/实况封面最终为 8bit，中转用 rgb24 即可（与 Pillow→JPEG 一致，且快很多）
JPEG_TRANSIT_PIX_FMT = "rgb24"


def extract_lossless_png(
    video_path: str,
    timestamp_sec: float,
    *,
    pix_fmt: str = PNG_LOSSLESS_PIX_FMT,
    video_info: VideoInfo | None = None,
) -> str:
    """
    精确解码截帧 → PNG 无损。

    性能：两阶段 -ss（粗定位 + 精确定位），避免长视频从 0 解码。
    画质：PNG 导出用 rgb48le；JPEG/实况封面中转可用 rgb24（最终 JPEG 仍为 q100/4:4:4）。
    """
    ffmpeg = resolve_tool("ffmpeg")
    info = video_info or probe_video(video_path)

    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix="pocket_lossless_", delete=False
    )
    tmp.close()
    png_path = tmp.name

    coarse = max(0.0, timestamp_sec - _SEEK_MARGIN_SEC)
    fine = max(0.0, timestamp_sec - coarse)

    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{coarse:.6f}",
        "-i",
        video_path,
        "-ss",
        f"{fine:.6f}",
        "-frames:v",
        "1",
        "-update",
        "1",
        "-c:v",
        "png",
        "-compression_level",
        "0",
        "-pred",
        "mixed",
        "-pix_fmt",
        pix_fmt,
        png_path,
    ]
    _run_ffmpeg(cmd, "PNG 无损截帧失败")

    path = Path(png_path)
    if not path.is_file() or path.stat().st_size < 1024:
        raise RuntimeError("截帧失败：输出无效")

    from PIL import Image

    with Image.open(path) as img:
        if img.size != (info.width, info.height):
            raise RuntimeError(
                f"截帧分辨率不符：期望 {info.width}×{info.height}，"
                f"实际 {img.size[0]}×{img.size[1]}"
            )
    return png_path


def transit_pix_fmt_for_export(enhance_mode: EnhanceMode) -> str:
    """PNG 成品用 rgb48le；仅 JPEG/封面中转且未做 AI 超分时用 rgb24。"""
    if enhance_mode == EnhanceMode.OFF:
        return JPEG_TRANSIT_PIX_FMT
    if is_realesrgan_mode(enhance_mode):
        return JPEG_TRANSIT_PIX_FMT
    return PNG_LOSSLESS_PIX_FMT


def _read_image_size(path: str) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as img:
        return img.size


def process_export_png(
    png_path: str,
    *,
    apply_watermark: bool = False,
    enhance_mode: EnhanceMode = EnhanceMode.OFF,
    on_progress: ProgressCallback | None = None,
) -> str | None:
    """截帧后处理：增强 → 水印。返回增强说明（若有）。"""
    enhance_note: str | None = None
    if enhance_mode != EnhanceMode.OFF:
        if on_progress:
            if is_realesrgan_mode(enhance_mode):
                on_progress(55, "AI 超分 2× 中（4K 约需 1～3 分钟，请耐心等待）…")
            else:
                on_progress(55, "轻度优化（锐化+降噪）…")
        _, enhance_note = enhance_png_file(
            png_path,
            mode=enhance_mode,
            on_progress=on_progress,
        )
    if apply_watermark:
        if on_progress:
            on_progress(92, "叠加水印…")
        apply_watermark_to_png_file(png_path)
    return enhance_note


def export_photo_png(
    video_path: str,
    timestamp_sec: float,
    output_path: str,
    *,
    apply_watermark: bool = False,
    enhance_mode: EnhanceMode = EnhanceMode.OFF,
    on_progress: ProgressCallback | None = None,
) -> str:
    """导出 PNG 无损照片，返回画质说明。"""
    output = Path(output_path)
    if output.suffix.lower() != ".png":
        output = output.with_suffix(".png")

    info = probe_video(video_path)
    if on_progress:
        on_progress(5, "PNG 无损截帧…")
    png_path = extract_lossless_png(
        video_path,
        timestamp_sec,
        pix_fmt=PNG_LOSSLESS_PIX_FMT,
        video_info=info,
    )
    try:
        enhance_note = process_export_png(
            png_path,
            apply_watermark=apply_watermark,
            enhance_mode=enhance_mode,
            on_progress=on_progress,
        )
        shutil.move(png_path, output)
    except Exception:
        Path(png_path).unlink(missing_ok=True)
        raise

    if enhance_mode != EnhanceMode.OFF:
        w, h = _read_image_size(str(output))
    else:
        w, h = info.width, info.height
    size_mb = output.stat().st_size / (1024 * 1024)
    if enhance_mode != EnhanceMode.OFF:
        note = (
            f"PNG · {info.width}×{info.height} → {w}×{h} · {size_mb:.1f} MB · "
            f"{enhance_note or '已增强'}"
        )
    else:
        note = f"PNG 无损 · {w}×{h} · {size_mb:.1f} MB"
    if apply_watermark:
        note += " · 已加水印"
    return note


def export_preview_png(
    video_path: str,
    timestamp_sec: float,
    output_path: str,
    *,
    apply_watermark: bool = False,
    enhance_mode: EnhanceMode = EnhanceMode.OFF,
) -> None:
    """实况预览页专用：PNG 截帧（预览用 rgb24 加速，不影响导出链路）。"""
    output = Path(output_path)
    if output.suffix.lower() != ".png":
        output = output.with_suffix(".png")

    info = probe_video(video_path)
    png_path = extract_lossless_png(
        video_path,
        timestamp_sec,
        pix_fmt=JPEG_TRANSIT_PIX_FMT,
        video_info=info,
    )
    try:
        process_export_png(
            png_path,
            apply_watermark=apply_watermark,
            enhance_mode=enhance_mode,
        )
        shutil.move(png_path, output)
    except Exception:
        Path(png_path).unlink(missing_ok=True)
        raise


def _run_ffmpeg(cmd: list[str], error_prefix: str) -> None:
    result = run_text(cmd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{error_prefix}: {detail}")
