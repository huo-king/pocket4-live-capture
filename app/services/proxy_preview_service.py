"""HEVC/H.265 预览代理 — 仅供 Qt 播放，导出仍用原片"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Callable

from app.services.subprocess_util import run_text
from app.services.tool_paths import resolve_tool
from app.services.video_probe import needs_preview_proxy, probe_video

ProgressCallback = Callable[[int, str], None]

# 代理最长边 1920，CRF 23 + veryfast，仅预览够用
PROXY_MAX_WIDTH = 1920


def proxy_cache_dir() -> Path:
    cache = Path(tempfile.gettempdir()) / "pocket_live_proxy"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def proxy_cache_path(source: str | Path) -> Path:
    src = Path(source).resolve()
    stat = src.stat()
    key = hashlib.sha256(
        f"{src}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    ).hexdigest()[:16]
    safe_stem = src.stem[:48] or "video"
    return proxy_cache_dir() / f"{safe_stem}_{key}_h264_preview.mp4"


def is_cache_valid(cache: Path, source: Path) -> bool:
    if not cache.is_file() or cache.stat().st_size < 4096:
        return False
    try:
        cached = probe_video(str(cache))
    except RuntimeError:
        return False
    if cached.codec.lower() not in ("h264", "avc1"):
        return False
    try:
        original = probe_video(str(source))
    except RuntimeError:
        return False
    if cached.duration_sec <= 0 or original.duration_sec <= 0:
        return True
    # 时长偏差超过 1 秒视为缓存失效
    return abs(cached.duration_sec - original.duration_sec) <= 1.0


def resolve_preview_path(source: str | Path) -> tuple[str, bool, Path | None]:
    """
    返回 (预览路径, 是否代理, 待生成缓存路径)。
    若需生成代理且缓存无效，第三项为目标缓存路径。
    """
    src = Path(source)
    info = probe_video(str(src))
    if not needs_preview_proxy(info.codec):
        return str(src.resolve()), False, None

    cache = proxy_cache_path(src)
    if is_cache_valid(cache, src):
        return str(cache), True, None
    return str(src.resolve()), True, cache


def generate_proxy(
    source: str | Path,
    output: str | Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> str:
    """将原片转码为 H.264 预览代理（含音频 AAC）。"""
    src = Path(source)
    dst = Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)

    info = probe_video(str(src))
    ffmpeg = resolve_tool("ffmpeg")

    scale = f"scale='min({PROXY_MAX_WIDTH},iw)':-2"
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vf",
        scale,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]
    if info.has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
    else:
        cmd.append("-an")
    cmd.append(str(dst))

    if on_progress:
        on_progress(5, "正在生成 H.264 预览代理…")

    result = run_text(cmd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"预览代理生成失败: {detail}")

    if not dst.is_file() or dst.stat().st_size < 4096:
        raise RuntimeError("预览代理输出无效")

    if on_progress:
        on_progress(100, "预览代理就绪")

    return str(dst)
