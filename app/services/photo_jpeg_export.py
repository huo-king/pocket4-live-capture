"""JPEG 最高质量照片导出 — 独立模块，与 PNG 导出分离"""

from __future__ import annotations

from pathlib import Path

from app.services.photo_png_export import extract_lossless_png
from app.services.photo_watermark import apply_watermark_to_png_file
from app.services.video_probe import probe_video


def export_photo_jpeg(
    video_path: str,
    timestamp_sec: float,
    output_path: str,
    *,
    apply_watermark: bool = False,
) -> str:
    """
    导出接近无损的 JPEG 照片。
    流程：PNG 无损截帧 → [可选水印] → Pillow quality=100 / subsampling=0（4:4:4）
    """
    output = Path(output_path)
    suffix = output.suffix.lower()
    if suffix not in (".jpg", ".jpeg"):
        output = output.with_suffix(".jpg")

    png_path = extract_lossless_png(video_path, timestamp_sec)
    try:
        if apply_watermark:
            apply_watermark_to_png_file(png_path)
        _png_to_jpeg_max(png_path, str(output))
    finally:
        Path(png_path).unlink(missing_ok=True)

    info = probe_video(video_path)
    size_mb = output.stat().st_size / (1024 * 1024)
    note = (
        f"JPEG 最高质量（PNG 无损中转，quality=100/4:4:4）· "
        f"{info.width}×{info.height} · {size_mb:.1f} MB"
    )
    if apply_watermark:
        note += " · 已加水印"
    return note


def export_motion_cover_jpeg(
    video_path: str,
    timestamp_sec: float,
    output_jpg: str,
    *,
    apply_watermark: bool = False,
) -> None:
    """
    实况封面：与照片 JPEG 相同链路（PNG 无损 → 最高质量 JPEG）。
    Motion Photo 规范要求外层为 .jpg，无法使用 PNG，但截帧阶段保持无损。
    """
    png_path = extract_lossless_png(video_path, timestamp_sec)
    try:
        if apply_watermark:
            apply_watermark_to_png_file(png_path)
        _png_to_jpeg_max(png_path, output_jpg)
    finally:
        Path(png_path).unlink(missing_ok=True)


def _png_to_jpeg_max(png_path: str, output_jpg: str) -> None:
    """PNG 无损 → Pillow JPEG quality=100 / 4:4:4（当前最高 JPEG 参数）。"""
    from PIL import Image

    with Image.open(png_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(
            output_jpg,
            format="JPEG",
            quality=100,
            subsampling=0,
            optimize=False,
            dpi=(300, 300),
        )

    out = Path(output_jpg)
    if not out.is_file() or out.stat().st_size < 1024:
        raise RuntimeError("JPEG 封装失败")
