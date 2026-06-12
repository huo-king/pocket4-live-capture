"""画质增强 — 独立模块，默认关闭，不影响现有无损导出链路。

适用范围
--------
1. 静帧：PNG / JPEG / 实况封面
2. 实况内嵌 MP4：约 3 秒片段（封面 + 视频可一并增强）

技术路线
--------
✅ Real-ESRGAN-ncnn-vulkan（tools/ 独立 exe，BSD，商用友好）
   - 静帧：单张 PNG 超分
   - 视频：拆帧 → 批量超分 → 高质量 H.264 重编码（含原音频）

⚠️ FFmpeg 轻度（锐化+降噪，单 pass，速度快，提升有限）

与「原画 stream copy」的关系
----------------------------
- 增强关闭：实况 MP4 仍 stream copy，零重编码（现有逻辑）
- 增强开启：实况 MP4 必须重编码，无法同时「AI 超分 + stream copy」
  · 3s @ 30fps ≈ 90 帧，2× 超分 GPU 约 3～8 分钟，CPU 更久
  · 输出体积通常明显大于原片码率 copy

部署
----
https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases
→ tools/realesrgan-ncnn-vulkan.exe + tools/models/
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.services.subprocess_util import run_text
from app.services.tool_paths import resolve_tool
from app.services.video_probe import probe_video

ProgressCallback = Callable[[int, str], None]

# 实况片段常见帧率兜底
_DEFAULT_FPS = 30.0


class EnhanceMode(str, Enum):
    """画质增强模式。OFF = 完全走现有逻辑，不做任何处理。"""

    OFF = "off"
    FFMPEG_LIGHT = "ffmpeg_light"
    REALESRGAN_COVER = "realesrgan_cover"
    REALESRGAN_FULL = "realesrgan_full"
    # 兼容旧值
    REALESRGAN_2X = "realesrgan_2x"
    REALESRGAN_4X = "realesrgan_4x"


DEFAULT_MODE = EnhanceMode.OFF
DEFAULT_ENHANCE_TIER = EnhanceMode.REALESRGAN_COVER

# 与 tools/models/ 中已安装模型一致（Pocket 实拍用 x4plus）
REALESRGAN_MODEL = "realesrgan-x4plus"
# x4plus 模型原生倍率；不可对其实用 -s 2（ncnn 已知 bug，输出会方块错位）
REALESRGAN_MODEL_SCALE = 4
# UI 开启时的目标倍率：先按模型原生 4× 超分，再 Lanczos 缩到 2×
REALESRGAN_SCALE_ON = 2

# --- 资源控制（防止吃满 GPU / CPU / 内存）---
# tile 越小越省显存，但越慢；256 约需 1~2GB VRAM，适合多数消费级显卡
REALESRGAN_TILE_SIZE = 256
# -j 格式 load:proc:save，限制线程避免系统卡死
REALESRGAN_THREADS = "2:2:2"
# 2× 模式优化：对 4K 源先缩到 1080p 再 4× 超分，计算量降至约 1/7
REALESRGAN_PRE_DOWNSCALE_FOR_2X = True


@dataclass(frozen=True)
class EnhanceTierOption:
    """勾选「画质增强」后下拉可选的档位（第 1 档「原画直出」= 不勾选）。"""

    mode: EnhanceMode
    label: str
    subtitle: str
    description: str


ENHANCE_TIER_OPTIONS: tuple[EnhanceTierOption, ...] = (
    EnhanceTierOption(
        EnhanceMode.FFMPEG_LIGHT,
        "轻度优化",
        "锐化+降噪 · 约几秒",
        "封面与实况内嵌视频均做轻度锐化降噪，速度快，适合日常。",
    ),
    EnhanceTierOption(
        EnhanceMode.REALESRGAN_COVER,
        "AI 封面超分",
        "封面 2× · 视频原画 · 1～3 分钟",
        "封面 AI 超分 2×（realesrgan-x4plus），内嵌 MP4 保持 stream copy 原画。",
    ),
    EnhanceTierOption(
        EnhanceMode.REALESRGAN_FULL,
        "AI 全量超分",
        "封面+视频 2× · 30～60 分钟",
        "封面与内嵌 MP4 均 AI 超分 2×，需独显与大内存，仅建议高配电脑。",
    ),
)


def normalize_enhance_mode(mode: EnhanceMode | str) -> EnhanceMode:
    coerced = coerce_enhance_mode(mode)
    if coerced is None:
        raise ValueError(f"未知增强模式: {mode!r}")
    if coerced == EnhanceMode.REALESRGAN_2X:
        return EnhanceMode.REALESRGAN_COVER
    if coerced == EnhanceMode.REALESRGAN_4X:
        return EnhanceMode.REALESRGAN_FULL
    return coerced


def coerce_enhance_mode(value: object) -> EnhanceMode | None:
    """QComboBox.currentData() 常返回 str 而非 Enum，需统一转换。"""
    if isinstance(value, EnhanceMode):
        return value
    if isinstance(value, str) and value:
        try:
            return EnhanceMode(value)
        except ValueError:
            return None
    return None


def is_realesrgan_mode(mode: EnhanceMode) -> bool:
    mode = normalize_enhance_mode(mode)
    return mode in (EnhanceMode.REALESRGAN_COVER, EnhanceMode.REALESRGAN_FULL)


def get_tier_option(mode: EnhanceMode) -> EnhanceTierOption | None:
    mode = normalize_enhance_mode(mode)
    for tier in ENHANCE_TIER_OPTIONS:
        if tier.mode == mode:
            return tier
    return None


def should_enhance_motion_video(mode: EnhanceMode) -> bool:
    """实况内嵌 MP4 是否做增强（轻度重编码或 AI 逐帧超分）。"""
    mode = normalize_enhance_mode(mode)
    if mode == EnhanceMode.FFMPEG_LIGHT:
        return True
    if mode == EnhanceMode.REALESRGAN_FULL:
        return True
    return False


def resolve_export_enhance_mode(mode: EnhanceMode) -> EnhanceMode:
    """导出前解析：无 Real-ESRGAN 时 AI 档位回退为轻度优化。"""
    mode = normalize_enhance_mode(mode)
    if mode == EnhanceMode.OFF:
        return EnhanceMode.OFF
    if is_realesrgan_mode(mode) and not is_realesrgan_available():
        return EnhanceMode.FFMPEG_LIGHT
    return mode


def resolve_enhance_mode(enabled: bool, tier: EnhanceMode = DEFAULT_ENHANCE_TIER) -> EnhanceMode:
    """兼容旧接口：勾选 + 档位 → 导出模式。"""
    if not enabled:
        return EnhanceMode.OFF
    return resolve_export_enhance_mode(tier)


@dataclass
class EnhanceVideoResult:
    output_path: str
    note: str
    frame_count: int
    reencoded: bool


def _tools_dir() -> Path:
    try:
        return Path(resolve_tool("ffmpeg")).parent
    except FileNotFoundError:
        return Path(__file__).resolve().parents[2] / "tools"


def resolve_realesrgan_exe() -> Path | None:
    tools = _tools_dir()
    candidates = [
        tools / "realesrgan-ncnn-vulkan.exe",
        tools / "realesrgan-ncnn-vulkan" / "realesrgan-ncnn-vulkan.exe",
        tools / "realesrgan-ncnn-vulkan" / "realesrgan-ncnn-vulkan",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def is_realesrgan_available() -> bool:
    return resolve_realesrgan_exe() is not None


def is_enhance_available(mode: EnhanceMode) -> bool:
    if mode == EnhanceMode.OFF:
        return True
    if mode == EnhanceMode.FFMPEG_LIGHT:
        try:
            resolve_tool("ffmpeg")
            return True
        except FileNotFoundError:
            return False
    if is_realesrgan_mode(mode):
        return is_realesrgan_available()
    return False


def describe_mode(mode: EnhanceMode) -> str:
    mode = normalize_enhance_mode(mode)
    tier = get_tier_option(mode)
    if tier is not None:
        return tier.label
    labels = {
        EnhanceMode.OFF: "原画直出（stream copy）",
    }
    return labels.get(mode, mode.value)


def estimate_video_enhance_seconds(
    *,
    width: int,
    height: int,
    duration_sec: float,
    fps: float,
    mode: EnhanceMode,
) -> int | None:
    """粗算实况 MP4 增强耗时（秒），供 UI 提示；None 表示几乎即时。"""
    if mode == EnhanceMode.OFF:
        return 0
    if mode == EnhanceMode.FFMPEG_LIGHT:
        return max(3, int(duration_sec * 2))
    if mode == EnhanceMode.REALESRGAN_COVER:
        return 0
    if mode == EnhanceMode.REALESRGAN_FULL:
        frame_count = max(1, int(duration_sec * (fps or _DEFAULT_FPS)))
        pixels = width * height
        per_frame = 3.0 if pixels <= 1920 * 1080 else 8.0
        return int(frame_count * per_frame) + 15
    return None


def enhance_png_file(
    input_png: str,
    output_png: str | None = None,
    *,
    mode: EnhanceMode = DEFAULT_MODE,
    on_progress: ProgressCallback | None = None,
) -> tuple[str, str]:
    """对 PNG 做画质增强，返回 (输出路径, 说明文字)。"""
    if mode == EnhanceMode.OFF:
        return input_png, "画质增强：关闭"

    src = Path(input_png)
    if not src.is_file():
        raise FileNotFoundError(f"输入不存在: {src}")

    if on_progress:
        on_progress(10, "正在增强封面…")

    if output_png is None:
        dst = src
        work_out = _temp_png(prefix="pocket_enh_out_")
        in_place = True
    else:
        dst = Path(output_png)
        work_out = str(dst)
        in_place = False

    if mode == EnhanceMode.FFMPEG_LIGHT:
        _enhance_ffmpeg_light(str(src), work_out)
        note = "封面 · 轻度增强（FFmpeg）"
    elif is_realesrgan_mode(mode):
        scale = _scale_for_mode(mode)
        _require_realesrgan()
        _enhance_realesrgan_ncnn(str(src), work_out, scale=scale)
        note = f"封面 · AI 超分 {scale}×（{REALESRGAN_MODEL}）"
    else:
        raise ValueError(f"未知增强模式: {mode}")

    if in_place:
        shutil.move(work_out, str(dst))

    if on_progress:
        on_progress(100, "封面增强完成")

    return str(dst), note


def enhance_video_clip(
    input_mp4: str,
    output_mp4: str,
    *,
    mode: EnhanceMode = DEFAULT_MODE,
    on_progress: ProgressCallback | None = None,
) -> EnhanceVideoResult:
    """
    增强实况内嵌 MP4 片段。

    输入通常为 stream copy 裁切后的 3s clip（含音频）。
    增强开启时会重编码视频轨；音频尽量 copy。
    """
    src = Path(input_mp4)
    dst = Path(output_mp4)
    if not src.is_file():
        raise FileNotFoundError(f"视频不存在: {src}")

    if mode == EnhanceMode.OFF:
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        info = probe_video(str(dst))
        return EnhanceVideoResult(
            output_path=str(dst),
            note="视频 · stream copy（未增强）",
            frame_count=max(1, int(info.duration_sec * (info.fps or _DEFAULT_FPS))),
            reencoded=False,
        )

    info = probe_video(str(src))
    fps = info.fps or _DEFAULT_FPS
    frame_count = max(1, int(info.duration_sec * fps))

    if on_progress:
        on_progress(5, f"准备增强实况视频（约 {frame_count} 帧）…")

    if mode == EnhanceMode.FFMPEG_LIGHT:
        _enhance_video_ffmpeg_light(str(src), str(dst), on_progress=on_progress)
        note = "视频 · 轻度增强 + H.264 重编码"
    elif is_realesrgan_mode(mode):
        scale = _scale_for_mode(mode)
        _require_realesrgan()
        _enhance_video_realesrgan(
            str(src),
            str(dst),
            scale=scale,
            fps=fps,
            on_progress=on_progress,
        )
        note = f"视频 · AI 超分 {scale}× + H.264 重编码（约 {frame_count} 帧）"
    else:
        raise ValueError(f"未知增强模式: {mode}")

    if on_progress:
        on_progress(100, "实况视频增强完成")

    return EnhanceVideoResult(
        output_path=str(dst),
        note=note,
        frame_count=frame_count,
        reencoded=True,
    )


def _require_realesrgan() -> None:
    if not is_realesrgan_available():
        raise RuntimeError(
            "未找到 Real-ESRGAN 工具。\n"
            "请将 realesrgan-ncnn-vulkan.exe 放到 tools/ 目录。\n"
            "下载：https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases"
        )


def _temp_png(*, prefix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix=prefix, delete=False)
    tmp.close()
    return tmp.name


def _enhance_ffmpeg_light(input_png: str, output_png: str) -> None:
    ffmpeg = resolve_tool("ffmpeg")
    vf = "hqdn3d=1.5:1.5:3:3,unsharp=5:5:0.6:5:5:0.0"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_png,
        "-vf",
        vf,
        "-frames:v",
        "1",
        "-c:v",
        "png",
        "-compression_level",
        "0",
        "-pix_fmt",
        "rgb48le",
        output_png,
    ]
    _run_ffmpeg(cmd, "FFmpeg 封面增强失败")


def _enhance_video_ffmpeg_light(
    input_mp4: str,
    output_mp4: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> None:
    ffmpeg = resolve_tool("ffmpeg")
    vf = "hqdn3d=1.5:1.5:3:3,unsharp=5:5:0.6:5:5:0.0"
    if on_progress:
        on_progress(30, "实况视频轻度增强中…")

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_mp4,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        "17",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        output_mp4,
    ]
    _run_ffmpeg(cmd, "FFmpeg 实况视频增强失败")


def _enhance_video_realesrgan(
    input_mp4: str,
    output_mp4: str,
    *,
    scale: int,
    fps: float,
    on_progress: ProgressCallback | None = None,
) -> None:
    work = Path(tempfile.mkdtemp(prefix="pocket_esr_video_"))
    frames_in = work / "in"
    frames_out = work / "out"
    frames_in.mkdir()
    frames_out.mkdir()

    try:
        if on_progress:
            on_progress(10, "拆解实况视频帧…")
        _extract_video_frames(input_mp4, frames_in)

        in_frames = sorted(frames_in.glob("*.png"))
        if not in_frames:
            raise RuntimeError("拆帧失败：未得到任何帧")

        # 2× 模式优化：先缩 50% 再 4× 超分，计算量降至 1/4，结果仍为 2× 原片
        esr_input_dir = frames_in
        if scale < REALESRGAN_MODEL_SCALE and REALESRGAN_PRE_DOWNSCALE_FOR_2X:
            orig_w, orig_h = _image_size(str(in_frames[0]))
            if orig_w > 1920 or orig_h > 1080:
                if on_progress:
                    on_progress(15, "预缩小帧（减少 GPU 负担）…")
                half_dir = work / "half"
                half_dir.mkdir()
                _downscale_png_dir(in_frames, half_dir, orig_w // 2, orig_h // 2)
                esr_input_dir = half_dir

        if on_progress:
            on_progress(
                25,
                f"AI 超分 {scale}×（{len(in_frames)} 帧，请耐心等待）…",
            )
        _enhance_realesrgan_ncnn(str(esr_input_dir), str(frames_out), scale=scale, folder=True)

        out_frames = sorted(frames_out.glob("*.png"))
        if len(out_frames) < len(in_frames):
            raise RuntimeError(
                f"超分帧数不足：输入 {len(in_frames)} 帧，输出 {len(out_frames)} 帧"
            )

        if on_progress:
            on_progress(75, "重编码实况 MP4…")
        _encode_frames_to_mp4(
            frames_out,
            input_mp4,
            output_mp4,
            fps=fps,
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _extract_video_frames(input_mp4: str, output_dir: Path) -> None:
    ffmpeg = resolve_tool("ffmpeg")
    pattern = str(output_dir / "frame_%06d.png")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_mp4,
        "-vsync",
        "0",
        pattern,
    ]
    _run_ffmpeg(cmd, "实况视频拆帧失败")


def _encode_frames_to_mp4(
    frames_dir: Path,
    source_mp4: str,
    output_mp4: str,
    *,
    fps: float,
) -> None:
    ffmpeg = resolve_tool("ffmpeg")
    pattern = str(frames_dir / "frame_%06d.png")
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        f"{fps:.6f}",
        "-i",
        pattern,
        "-i",
        source_mp4,
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "libx264",
        "-crf",
        "17",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-shortest",
        "-movflags",
        "+faststart",
        output_mp4,
    ]
    _run_ffmpeg(cmd, "实况视频重编码失败")


def _scale_for_mode(mode: EnhanceMode) -> int:
    mode = normalize_enhance_mode(mode)
    if mode == EnhanceMode.REALESRGAN_FULL:
        return REALESRGAN_SCALE_ON
    if is_realesrgan_mode(mode):
        return REALESRGAN_SCALE_ON
    return REALESRGAN_SCALE_ON


def _image_size(path: str) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as img:
        return img.size


def _needs_rgb8_for_realesrgan(path: str) -> bool:
    """rgb48le 等高位深 PNG 需转为 8bit RGB，否则 ncnn 可能异常。"""
    from PIL import Image

    with Image.open(path) as img:
        if img.mode != "RGB":
            return True
        sample = img.getpixel((0, 0))
        if isinstance(sample, tuple):
            return any(v > 255 for v in sample)
        return int(sample) > 255


def _ensure_realesrgan_input(input_path: str) -> tuple[str, Path | None]:
    """返回 Real-ESRGAN 可读的 8bit RGB 路径；必要时写入临时文件。"""
    if not _needs_rgb8_for_realesrgan(input_path):
        return input_path, None

    from PIL import Image

    tmp = Path(_temp_png(prefix="pocket_esr_in_"))
    with Image.open(input_path) as img:
        img.convert("RGB").save(tmp, format="PNG", compress_level=0)
    return str(tmp), tmp


def _downscale_png_to_target(
    png_path: str,
    orig_w: int,
    orig_h: int,
    target_scale: int,
) -> None:
    """将 Real-ESRGAN 4× 输出 Lanczos 缩至目标倍率。"""
    from PIL import Image

    target_w = orig_w * target_scale
    target_h = orig_h * target_scale
    with Image.open(png_path) as img:
        resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        resized.save(png_path, format="PNG", compress_level=0)


def _downscale_png_dir(
    src_dir: Path,
    dst_dir: Path,
    target_w: int,
    target_h: int,
) -> None:
    """批量缩小 PNG 到指定分辨率（用于 ESR 前置缩小）。"""
    from PIL import Image

    for frame in sorted(src_dir.glob("*.png")):
        with Image.open(frame) as img:
            resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            resized.save(dst_dir / frame.name, format="PNG", compress_level=0)


def _downscale_png_dir_to_target(
    frames_dir: Path,
    orig_w: int,
    orig_h: int,
    target_scale: int,
) -> None:
    for frame in sorted(frames_dir.glob("*.png")):
        _downscale_png_to_target(str(frame), orig_w, orig_h, target_scale)


def _enhance_realesrgan_ncnn(
    input_path: str,
    output_path: str,
    *,
    scale: int,
    folder: bool = False,
) -> None:
    exe = resolve_realesrgan_exe()
    if exe is None:
        raise RuntimeError("Real-ESRGAN 可执行文件未找到")

    tools = exe.parent
    input_tmp: Path | None = None
    half_tmp: Path | None = None
    realesrgan_input = input_path
    skip_post_downscale = False

    if folder:
        in_frames = sorted(Path(input_path).glob("*.png"))
        if not in_frames:
            raise RuntimeError("超分输入目录为空")
        orig_w, orig_h = _image_size(str(in_frames[0]))
    else:
        realesrgan_input, input_tmp = _ensure_realesrgan_input(input_path)
        orig_w, orig_h = _image_size(input_path)
        if (
            scale < REALESRGAN_MODEL_SCALE
            and REALESRGAN_PRE_DOWNSCALE_FOR_2X
            and (orig_w > 1920 or orig_h > 1080)
        ):
            half_w, half_h = orig_w // 2, orig_h // 2
            half_tmp = Path(_temp_png(prefix="pocket_esr_half_"))
            _downscale_png_to_absolute(str(realesrgan_input), str(half_tmp), half_w, half_h)
            realesrgan_input = str(half_tmp)
            orig_w, orig_h = half_w, half_h
            skip_post_downscale = True

    # realesrgan-x4plus 必须用原生 -s 4；对 x4 模型传 -s 2 会导致 tile 方块错位
    cmd = [
        str(exe),
        "-i",
        realesrgan_input,
        "-o",
        output_path,
        "-n",
        REALESRGAN_MODEL,
        "-s",
        str(REALESRGAN_MODEL_SCALE),
        "-t",
        str(REALESRGAN_TILE_SIZE),
        "-j",
        REALESRGAN_THREADS,
        "-f",
        "png",
    ]

    try:
        result = run_text(cmd, cwd=str(tools))
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Real-ESRGAN 增强失败: {detail}")

        if scale < REALESRGAN_MODEL_SCALE and not skip_post_downscale:
            if folder:
                _downscale_png_dir_to_target(
                    Path(output_path), orig_w, orig_h, scale
                )
            else:
                _downscale_png_to_target(output_path, orig_w, orig_h, scale)

        if not folder:
            out = Path(output_path)
            if not out.is_file() or out.stat().st_size < 1024:
                raise RuntimeError("Real-ESRGAN 输出无效，请检查 models 是否完整")
    finally:
        if input_tmp is not None:
            input_tmp.unlink(missing_ok=True)
        if half_tmp is not None:
            half_tmp.unlink(missing_ok=True)


def _downscale_png_to_absolute(
    png_path: str,
    output_path: str,
    target_w: int,
    target_h: int,
) -> None:
    from PIL import Image

    with Image.open(png_path) as img:
        resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        resized.save(output_path, format="PNG", compress_level=0)


def _run_ffmpeg(cmd: list[str], error_prefix: str) -> None:
    result = run_text(cmd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{error_prefix}: {detail}")
