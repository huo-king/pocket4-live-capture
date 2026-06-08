"""PNG 无损照片导出 — 独立模块，与 JPEG 导出分离"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.services.photo_watermark import apply_watermark_to_png_file
from app.services.subprocess_util import run_text
from app.services.tool_paths import resolve_tool
from app.services.video_probe import probe_video


def extract_lossless_png(video_path: str, timestamp_sec: float) -> str:
    """
    精确解码截帧 → PNG 无损。
    -ss 在 -i 之后：逐帧精确解码
    rgb48le：保留更多色彩位深（10bit 源不会压成 8bit）
    """
    ffmpeg = resolve_tool("ffmpeg")
    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix="pocket_lossless_", delete=False
    )
    tmp.close()
    png_path = tmp.name

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        video_path,
        "-ss",
        f"{timestamp_sec:.6f}",
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
        "rgb48le",
        png_path,
    ]
    _run_ffmpeg(cmd, "PNG 无损截帧失败")

    path = Path(png_path)
    if not path.is_file() or path.stat().st_size < 1024:
        raise RuntimeError("截帧失败：输出无效")

    info = probe_video(video_path)
    from PIL import Image

    with Image.open(path) as img:
        if img.size != (info.width, info.height):
            raise RuntimeError(
                f"截帧分辨率不符：期望 {info.width}×{info.height}，"
                f"实际 {img.size[0]}×{img.size[1]}"
            )
    return png_path


def export_photo_png(
    video_path: str,
    timestamp_sec: float,
    output_path: str,
    *,
    apply_watermark: bool = False,
) -> str:
    """导出 PNG 无损照片，返回画质说明。"""
    output = Path(output_path)
    if output.suffix.lower() != ".png":
        output = output.with_suffix(".png")

    png_path = extract_lossless_png(video_path, timestamp_sec)
    try:
        if apply_watermark:
            apply_watermark_to_png_file(png_path)
        shutil.move(png_path, output)
    except Exception:
        Path(png_path).unlink(missing_ok=True)
        raise

    info = probe_video(video_path)
    size_mb = output.stat().st_size / (1024 * 1024)
    note = f"PNG 无损 · {info.width}×{info.height} · {size_mb:.1f} MB"
    if apply_watermark:
        note += " · 已加水印"
    return note


def export_preview_png(
    video_path: str,
    timestamp_sec: float,
    output_path: str,
    *,
    apply_watermark: bool = False,
) -> None:
    """实况预览页专用：PNG 无损截帧（仅显示，不经过 JPEG 压缩）。"""
    output = Path(output_path)
    if output.suffix.lower() != ".png":
        output = output.with_suffix(".png")

    png_path = extract_lossless_png(video_path, timestamp_sec)
    try:
        if apply_watermark:
            apply_watermark_to_png_file(png_path)
        shutil.move(png_path, output)
    except Exception:
        Path(png_path).unlink(missing_ok=True)
        raise


def _run_ffmpeg(cmd: list[str], error_prefix: str) -> None:
    result = run_text(cmd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{error_prefix}: {detail}")
