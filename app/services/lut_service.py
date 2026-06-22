"""LUT 色彩查找表 — FFmpeg lut3d + blend，PNG 保持 rgb48le 无损链路。"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.services.lut_presets import BUILTIN_LUT_PRESETS, generate_builtin_lut_files
from app.services.subprocess_util import run_text
from app.services.tool_paths import PROJECT_ROOT, resolve_tool

FFMPEG_LIGHT_VF = "hqdn3d=1.5:1.5:3:3,unsharp=5:5:0.6:5:5:0.0"
_MOTION_LUT_CRF = "16"
_MOTION_LUT_PRESET = "slow"
DEFAULT_BUILTIN_LUT_FILENAME = BUILTIN_LUT_PRESETS[0].filename


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal = exe_dir / "_internal"
        if internal.is_dir():
            return internal
        return exe_dir
    return PROJECT_ROOT


def bundled_lut_dir() -> Path:
    return _bundle_root() / "app" / "assets" / "luts"


def user_lut_dir() -> Path:
    folder = Path.home() / "Pictures" / "PocketLiveCapture" / "luts"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def ensure_lut_assets_dir() -> Path:
    bundled = bundled_lut_dir()
    bundled.mkdir(parents=True, exist_ok=True)
    ensure_builtin_luts(bundled)
    return bundled


def ensure_builtin_luts(target_dir: Path | None = None) -> None:
    """确保内置预设 .cube 存在且轴顺序与 FFmpeg 一致。"""
    folder = target_dir or bundled_lut_dir()
    folder.mkdir(parents=True, exist_ok=True)
    from app.services.lut_presets import CUBE_FORMAT_MARKER

    stale = [
        p
        for p in BUILTIN_LUT_PRESETS
        if not (folder / p.filename).is_file()
        or CUBE_FORMAT_MARKER
        not in (folder / p.filename).read_text(encoding="utf-8", errors="replace")[
            :512
        ]
    ]
    if stale:
        generate_builtin_lut_files(folder)


def list_builtin_luts() -> list[Path]:
    folder = ensure_lut_assets_dir()
    presets = [folder / p.filename for p in BUILTIN_LUT_PRESETS]
    return [p for p in presets if p.is_file()]


def list_user_luts() -> list[Path]:
    folder = user_lut_dir()
    return sorted(folder.glob("*.cube"))


def list_available_luts() -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in list_builtin_luts() + list_user_luts():
        key = path.name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def preset_label_for_path(path: str | Path) -> str:
    name = Path(path).name
    for preset in BUILTIN_LUT_PRESETS:
        if preset.filename == name:
            return preset.label
    return Path(path).stem


def default_builtin_lut_path() -> str:
    luts = list_builtin_luts()
    if luts:
        return str(luts[0])
    folder = ensure_lut_assets_dir()
    return str(folder / DEFAULT_BUILTIN_LUT_FILENAME)


@dataclass(frozen=True)
class LutConfig:
    enabled: bool = False
    lut_path: str = ""
    strength: int = 100
    stack_lut_path: str = ""
    stack_strength: int = 100

    def active_layers(self) -> tuple[tuple[str, int], ...]:
        if not self.enabled:
            return ()
        layers: list[tuple[str, int]] = []
        if self.lut_path and Path(self.lut_path).is_file() and self.strength > 0:
            layers.append((self.lut_path, self.strength))
        if (
            self.stack_lut_path
            and Path(self.stack_lut_path).is_file()
            and self.stack_strength > 0
            and self.stack_lut_path != self.lut_path
        ):
            layers.append((self.stack_lut_path, self.stack_strength))
        return tuple(layers)

    @property
    def active(self) -> bool:
        return bool(self.active_layers())


LUT_DISABLED = LutConfig(enabled=False)


def is_valid_cube_file(path: str | Path) -> bool:
    cube = Path(path)
    if not cube.is_file() or cube.suffix.lower() != ".cube":
        return False
    try:
        head = cube.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return False
    if "LUT_3D_SIZE" not in head.upper():
        return False
    return bool(re.search(r"^\s*[\d.eE+-]+\s+[\d.eE+-]+\s+[\d.eE+-]+\s*$", head, re.M))


def import_lut_file(source: str | Path) -> Path:
    src = Path(source)
    if not is_valid_cube_file(src):
        raise ValueError("无效的 .cube LUT 文件（需包含 LUT_3D_SIZE 与 RGB 数据）")
    dest_dir = user_lut_dir()
    safe_name = re.sub(r"[^\w.\-]", "_", src.name)
    dest = dest_dir / safe_name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def describe_lut(config: LutConfig) -> str:
    if not config.enabled:
        return "LUT 调色 · 关闭"
    layers = config.active_layers()
    if not layers:
        return "LUT 调色 · 文件缺失（已跳过）"
    parts = [
        f"{preset_label_for_path(path)} {strength}%"
        for path, strength in layers
    ]
    return "LUT 调色 · " + " + ".join(parts)


def _ffmpeg_lut_path(lut_path: str) -> str:
    """FFmpeg 滤镜路径：正斜杠 + 转义 Windows 盘符冒号。"""
    p = str(Path(lut_path).resolve()).replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = f"{p[0]}\\:{p[2:]}"
    return p.replace("'", r"'\''")


def _build_single_layer_vf(lut_path: str, strength: int, index: int) -> str:
    cube = _ffmpeg_lut_path(lut_path)
    opacity_val = max(0, min(100, strength)) / 100.0
    if opacity_val >= 0.999:
        return f"lut3d=file='{cube}'"
    opacity = f"{opacity_val:.4f}"
    return (
        f"split[orig{index}][main{index}];[main{index}]lut3d=file='{cube}'[luted{index}];"
        f"[orig{index}][luted{index}]blend=all_opacity={opacity}"
    )


def build_lut_vf(config: LutConfig, *, extra_vf: str = "") -> str:
    layers = config.active_layers()
    if not layers:
        raise ValueError("LUT 未启用")
    lut_part = ",".join(
        _build_single_layer_vf(path, strength, index)
        for index, (path, strength) in enumerate(layers)
    )
    if extra_vf:
        return f"{lut_part},{extra_vf}"
    return lut_part


def _detect_png_pix_fmt(png_path: str) -> str:
    from PIL import Image

    with Image.open(png_path) as img:
        if img.mode == "RGB" and getattr(img, "bits", 8) >= 16:
            return "rgb48le"
        if img.mode in ("I;16", "RGB"):
            return "rgb48le" if img.mode == "I;16" else "rgb24"
    return "rgb48le"


def apply_lut_to_png(png_path: str, config: LutConfig) -> str | None:
    if not config.active:
        return None
    src = Path(png_path)
    if not src.is_file():
        raise FileNotFoundError(f"PNG 不存在: {png_path}")

    pix_fmt = _detect_png_pix_fmt(png_path)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix="pocket_lut_", delete=False
    )
    tmp.close()
    out_path = tmp.name

    ffmpeg = resolve_tool("ffmpeg")
    vf = build_lut_vf(config)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-frames:v",
        "1",
        "-c:v",
        "png",
        "-compression_level",
        "0",
        "-pred",
        "mixed",
        "-pix_fmt",
        pix_fmt,
        out_path,
    ]
    _run_ffmpeg(cmd, "LUT 调色失败（PNG）")
    out = Path(out_path)
    if not out.is_file() or out.stat().st_size < 1024:
        out.unlink(missing_ok=True)
        raise RuntimeError("LUT 输出无效")
    shutil.move(out_path, png_path)
    return describe_lut(config)


def apply_lut_to_video(
    input_mp4: str,
    output_mp4: str,
    config: LutConfig,
    *,
    extra_vf: str = "",
) -> None:
    if not config.active:
        raise ValueError("LUT 未启用")
    vf = build_lut_vf(config, extra_vf=extra_vf)
    ffmpeg = resolve_tool("ffmpeg")
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
        _MOTION_LUT_CRF,
        "-preset",
        _MOTION_LUT_PRESET,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        output_mp4,
    ]
    _run_ffmpeg(cmd, "LUT 调色失败（视频）")
    out = Path(output_mp4)
    if not out.is_file() or out.stat().st_size < 1024:
        raise RuntimeError("LUT 视频输出无效")


def ffmpeg_light_vf_for_lut() -> str:
    return FFMPEG_LIGHT_VF


def _run_ffmpeg(cmd: list[str], error_prefix: str) -> None:
    result = run_text(cmd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{error_prefix}: {detail}")
