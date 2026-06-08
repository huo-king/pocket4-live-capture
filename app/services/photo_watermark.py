"""照片 / 实况封面水印 — 独立模块，像素级叠加，不改变导出编码参数"""

from __future__ import annotations

import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image

from app.services.subprocess_util import run_text
from app.services.tool_paths import _bundle_root, resolve_tool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WATERMARK_FILENAME = "watermark_osmo_pocket4.png"

# 参照 Pocket 实拍效果（图2）：logo 宽度 ≈ 画面宽 18%，等比例缩放
WATERMARK_WIDTH_RATIO = 0.18
# 底边留白 ≈ 水印高度的 1.75 倍（与实拍一致，不贴死底边）
BOTTOM_MARGIN_HEIGHT_FACTOR = 1.75


def resolve_watermark_path() -> Path:
    """查找水印 PNG：打包目录 / 项目 app/assets / 项目根目录兼容名。"""
    bundle = _bundle_root()
    candidates = [
        bundle / "app" / "assets" / WATERMARK_FILENAME,
        bundle / "assets" / WATERMARK_FILENAME,
    ]
    if not getattr(sys, "frozen", False):
        candidates.append(PROJECT_ROOT / "dajiangphoto[1].png")

    for path in candidates:
        if path.is_file():
            return path

    raise FileNotFoundError(
        f"未找到水印文件 {WATERMARK_FILENAME}，"
        f"请放到 {bundle / 'app' / 'assets'}"
    )


@lru_cache(maxsize=1)
def _cropped_watermark_source() -> Image.Image:
    """
    裁掉素材四周透明/空白区域，只保留 logo 本体。
    原图 7680×4320 但 logo 仅在中间一条，不裁剪会导致位置偏上。
    """
    source = Image.open(resolve_watermark_path()).convert("RGBA")
    bbox = source.getbbox()
    if bbox is None:
        raise RuntimeError("水印素材无效：无可见内容")
    return source.crop(bbox)


def _watermark_layout(frame_w: int, frame_h: int) -> tuple[Image.Image, int]:
    """按画面尺寸等比例计算水印大小与底边距。"""
    logo = _cropped_watermark_source()

    target_w = max(1, int(frame_w * WATERMARK_WIDTH_RATIO))
    scale = target_w / logo.width
    target_h = max(1, int(logo.height * scale))
    wm = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)

    margin_y = max(6, int(target_h * BOTTOM_MARGIN_HEIGHT_FACTOR))
    return wm, margin_y


def _frame_size(png_path: str) -> tuple[int, int]:
    with Image.open(png_path) as img:
        return img.size


def apply_watermark_to_png_file(png_path: str) -> None:
    """
    在 PNG 文件上叠加水印（原地覆盖）。
    使用 FFmpeg overlay + rgb48le，保持与截帧相同的 PNG 无损参数。
    """
    path = Path(png_path)
    frame_w, frame_h = _frame_size(png_path)
    wm, margin_y = _watermark_layout(frame_w, frame_h)

    wm_tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix="pocket_wm_", delete=False
    )
    wm_tmp.close()
    wm_path = wm_tmp.name

    # 临时文件与目标同目录，避免 C:→D: 跨盘符移动失败
    out_tmp = tempfile.NamedTemporaryFile(
        suffix=".png",
        prefix="pocket_wm_out_",
        dir=str(path.parent),
        delete=False,
    )
    out_tmp.close()
    out_path = out_tmp.name
    moved = False

    try:
        wm.save(wm_path, format="PNG")

        ffmpeg = resolve_tool("ffmpeg")
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(path),
            "-i",
            wm_path,
            "-filter_complex",
            f"overlay=(W-w)/2:H-h-{margin_y}",
            "-frames:v",
            "1",
            "-c:v",
            "png",
            "-compression_level",
            "0",
            "-pred",
            "mixed",
            "-pix_fmt",
            "rgb48le",
            out_path,
        ]
        result = run_text(cmd)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"水印叠加失败: {detail}")

        shutil.move(out_path, path)
        moved = True
    finally:
        Path(wm_path).unlink(missing_ok=True)
        if not moved:
            Path(out_path).unlink(missing_ok=True)


def apply_watermark_to_image(base: Image.Image) -> Image.Image:
    """将水印叠到 PIL 图像上（JPEG 中转前合成）。"""
    frame = base.convert("RGBA")
    wm, margin_y = _watermark_layout(frame.width, frame.height)

    x = max(0, (frame.width - wm.width) // 2)
    y = max(0, frame.height - wm.height - margin_y)

    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    layer.paste(wm, (x, y), wm)
    return Image.alpha_composite(frame, layer)
