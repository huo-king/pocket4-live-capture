"""内置 LUT 预设 — 程序生成 .cube，可自由使用（MIT / 公有领域）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

Transform = Callable[[float, float, float], tuple[float, float, float]]

LUT_CUBE_SIZE = 17
# FFmpeg lut3d / Adobe .cube：R 变化最快，B 最慢（B 外层循环）
CUBE_FORMAT_MARKER = "# POCKET_CUBE_ORDER=rgb_fastest"


@dataclass(frozen=True)
class LutPreset:
    filename: str
    label: str
    title: str
    description: str
    transform: Transform


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _luma(r: float, g: float, b: float) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def _warm_sunset(r: float, g: float, b: float) -> tuple[float, float, float]:
    return r * 1.08 + 0.02, g * 1.03 + 0.01, b * 0.90


def _cool_cinematic(r: float, g: float, b: float) -> tuple[float, float, float]:
    return r * 0.93, g * 0.97 + 0.01, b * 1.10 + 0.02


def _vintage_film(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = _luma(r, g, b)
    ro = _lerp(l, r, 0.72) * 0.94 + 0.05
    go = _lerp(l, g, 0.72) * 0.90 + 0.04
    bo = _lerp(l, b, 0.68) * 0.86 + 0.03
    return ro, go, bo


def _teal_orange(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = _luma(r, g, b)
    shadow = max(0.0, min(1.0, (0.45 - l) / 0.45))
    highlight = max(0.0, min(1.0, (l - 0.40) / 0.55))
    sr = r * (1.0 - 0.12 * shadow) + 0.02 * shadow
    sg = g * (1.0 - 0.04 * shadow) + 0.10 * shadow
    sb = b * (1.0 - 0.02 * shadow) + 0.14 * shadow
    ro = sr * (1.0 - highlight) + (sr * 1.12 + 0.04) * highlight
    go = sg * (1.0 - highlight) + (sg * 1.06 + 0.02) * highlight
    bo = sb * (1.0 - highlight) + sb * 0.82 * highlight
    return ro, go, bo


def _vivid_pop(r: float, g: float, b: float) -> tuple[float, float, float]:
    r = _clamp(r**0.90)
    g = _clamp(g**0.90)
    b = _clamp(b**0.90)
    l = _luma(r, g, b)
    sat = 1.18
    return l + (r - l) * sat, l + (g - l) * sat, l + (b - l) * sat


def _soft_portrait(r: float, g: float, b: float) -> tuple[float, float, float]:
    r = r * 0.90 + 0.07
    g = g * 0.90 + 0.07
    b = b * 0.90 + 0.07
    return r * 1.04 + 0.01, g * 1.02, b * 0.96


def _high_contrast(r: float, g: float, b: float) -> tuple[float, float, float]:
    def curve(x: float) -> float:
        x = _clamp(x)
        if x < 0.5:
            return 2.0 * x * x
        return 1.0 - 2.0 * (1.0 - x) * (1.0 - x)

    return curve(r), curve(g), curve(b)


BUILTIN_LUT_PRESETS: tuple[LutPreset, ...] = (
    LutPreset(
        "01_soft_portrait.cube",
        "柔肤人像",
        "Pocket Soft Portrait",
        "轻微提亮 + 暖肤，适合人物与 vlog。",
        _soft_portrait,
    ),
    LutPreset(
        "02_warm_sunset.cube",
        "暖色日落",
        "Pocket Warm Sunset",
        "偏暖金色调，户外/黄昏氛围。",
        _warm_sunset,
    ),
    LutPreset(
        "03_cool_cinematic.cube",
        "冷色电影",
        "Pocket Cool Cinematic",
        "偏冷蓝阴影，城市/夜景电影感。",
        _cool_cinematic,
    ),
    LutPreset(
        "04_teal_orange.cube",
        "青橙大片",
        "Pocket Teal Orange",
        "经典青橙分离，旅行/风光。",
        _teal_orange,
    ),
    LutPreset(
        "05_vintage_film.cube",
        "复古胶片",
        "Pocket Vintage Film",
        "褪色胶片感，怀旧色调。",
        _vintage_film,
    ),
    LutPreset(
        "06_vivid_pop.cube",
        "鲜活饱和",
        "Pocket Vivid Pop",
        "适度提饱和与对比，色彩更跳。",
        _vivid_pop,
    ),
    LutPreset(
        "07_high_contrast.cube",
        "高对比",
        "Pocket High Contrast",
        "S 曲线增强明暗对比。",
        _high_contrast,
    ),
)


def write_cube_file(path: Path, preset: LutPreset, *, size: int = LUT_CUBE_SIZE) -> None:
    lines = [
        f'TITLE "{preset.title}"',
        f"# {preset.description}",
        "# Pocket Live Capture built-in preset (free to use)",
        CUBE_FORMAT_MARKER,
        f"LUT_3D_SIZE {size}",
        "",
    ]
    denom = max(1, size - 1)
    # FFmpeg .cube 读入顺序：blue 最慢 → green → red 最快
    for bi in range(size):
        b = bi / denom
        for gi in range(size):
            g = gi / denom
            for ri in range(size):
                r = ri / denom
                ro, go, bo = preset.transform(r, g, b)
                lines.append(
                    f"{_clamp(ro):.6f} {_clamp(go):.6f} {_clamp(bo):.6f}"
                )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_builtin_lut_files(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for preset in BUILTIN_LUT_PRESETS:
        dest = output_dir / preset.filename
        write_cube_file(dest, preset)
        written.append(dest)
    return written
