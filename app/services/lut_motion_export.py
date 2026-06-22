"""实况视频 LUT 处理 — 与增强档位组合，尽量单次重编码。"""

from __future__ import annotations

from pathlib import Path

from app.services.lut_service import (
    LutConfig,
    apply_lut_to_video,
    ffmpeg_light_vf_for_lut,
)
from app.services.quality_enhance_service import (
    EnhanceMode,
    ProgressCallback,
    enhance_video_clip,
    should_enhance_motion_video,
)


def should_apply_lut_to_motion_video(
    lut_config: LutConfig,
    enhance_mode: EnhanceMode,
) -> bool:
    """内嵌 MP4 是否走 LUT（REALESRGAN_COVER 仅封面 LUT，视频 stream copy）。"""
    if not lut_config.active:
        return False
    if enhance_mode == EnhanceMode.REALESRGAN_COVER:
        return False
    return True


def apply_lut_to_motion_clip(
    clip_path: str,
    output_path: str,
    lut_config: LutConfig,
    enhance_mode: EnhanceMode,
    *,
    on_progress: ProgressCallback | None = None,
) -> tuple[str, str]:
    """
    对实况内嵌 MP4 应用 LUT（及可选增强）。
    返回 (最终路径, 画质说明)。
    """
    if not lut_config.active:
        return clip_path, ""

    src = clip_path
    mode = enhance_mode
    enhance_video = should_enhance_motion_video(mode)

    if not enhance_video:
        if on_progress:
            on_progress(52, "实况视频 LUT 调色（高质量 H.264）…")
        apply_lut_to_video(src, output_path, lut_config)
        note = f"视频 · LUT 调色 · CRF16 · {lut_config.strength}%"
        return output_path, note

    if mode == EnhanceMode.FFMPEG_LIGHT:
        if on_progress:
            on_progress(52, "LUT + 轻度增强（单次重编码）…")
        apply_lut_to_video(
            src,
            output_path,
            lut_config,
            extra_vf=ffmpeg_light_vf_for_lut(),
        )
        return output_path, "视频 · LUT + 轻度增强 · 单次重编码"

    if on_progress:
        on_progress(52, "实况视频 LUT 调色…")
    lut_only = str(Path(output_path).with_name("clip_lut.mp4"))
    apply_lut_to_video(src, lut_only, lut_config)

    if on_progress:
        on_progress(58, "LUT 完成后 AI 增强视频…")

    def mapped_progress(value: int, message: str) -> None:
        if on_progress:
            on_progress(58 + int(value * 0.32), message)

    result = enhance_video_clip(
        lut_only,
        output_path,
        mode=mode,
        on_progress=mapped_progress,
    )
    return output_path, f"LUT + {result.note}"
