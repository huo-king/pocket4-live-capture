"""JPEG 最高质量照片导出 — 独立模块，与 PNG 导出分离"""

from __future__ import annotations

from pathlib import Path

from app.services.photo_png_export import (
    extract_lossless_png,
    process_export_png,
    transit_pix_fmt_for_export,
    _read_image_size,
)
from app.services.quality_enhance_service import EnhanceMode, ProgressCallback
from app.services.video_probe import VideoInfo, probe_video


def export_photo_jpeg(
    video_path: str,
    timestamp_sec: float,
    output_path: str,
    *,
    apply_watermark: bool = False,
    enhance_mode: EnhanceMode = EnhanceMode.OFF,
    on_progress: ProgressCallback | None = None,
) -> str:
    """
    导出接近无损的 JPEG 照片。
    流程：PNG 无损截帧 → [可选增强] → [可选水印] → Pillow quality=100 / subsampling=0（4:4:4）
    """
    output = Path(output_path)
    suffix = output.suffix.lower()
    if suffix not in (".jpg", ".jpeg"):
        output = output.with_suffix(".jpg")

    info = probe_video(video_path)
    if on_progress:
        on_progress(5, "PNG 无损截帧…")
    png_path = extract_lossless_png(
        video_path,
        timestamp_sec,
        pix_fmt=transit_pix_fmt_for_export(enhance_mode),
        video_info=info,
    )
    try:
        enhance_note = process_export_png(
            png_path,
            apply_watermark=apply_watermark,
            enhance_mode=enhance_mode,
            on_progress=on_progress,
        )
        if on_progress:
            on_progress(95, "封装 JPEG…")
        _png_to_jpeg_max(png_path, str(output))
    finally:
        Path(png_path).unlink(missing_ok=True)

    if enhance_mode != EnhanceMode.OFF:
        w, h = _read_image_size(str(output))
        orig_w, orig_h = info.width, info.height
    else:
        w, h = info.width, info.height
        orig_w, orig_h = w, h
    size_mb = output.stat().st_size / (1024 * 1024)
    if enhance_mode != EnhanceMode.OFF:
        note = (
            f"JPEG（{orig_w}×{orig_h} → {w}×{h} · "
            f"{enhance_note or '已增强'} → quality=100/4:4:4）· "
            f"{size_mb:.1f} MB"
        )
    else:
        note = (
            f"JPEG 最高质量（PNG 无损中转，quality=100/4:4:4）· "
            f"{w}×{h} · {size_mb:.1f} MB"
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
    enhance_mode: EnhanceMode = EnhanceMode.OFF,
    video_info: VideoInfo | None = None,
) -> str | None:
    """
    实况封面：PNG 中转 → [增强] → [水印] → JPEG(q100/4:4:4)。
    未增强时用 rgb24 中转（与 JPEG 输出位深一致，更快）。
    """
    info = video_info or probe_video(video_path)
    png_path = extract_lossless_png(
        video_path,
        timestamp_sec,
        pix_fmt=transit_pix_fmt_for_export(enhance_mode),
        video_info=info,
    )
    try:
        enhance_note = process_export_png(
            png_path,
            apply_watermark=apply_watermark,
            enhance_mode=enhance_mode,
        )
        _png_to_jpeg_max(png_path, output_jpg)
        return enhance_note
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
