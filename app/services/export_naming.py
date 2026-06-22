"""导出默认文件名与序号分配 — 普通/增强区分后缀，避免重复导出冲突。"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

from app.services.quality_enhance_service import EnhanceMode, resolve_export_enhance_mode

ENHANCE_SUFFIX = "_enh"
LUT_SUFFIX = "_lut"
_SEQ_RE = re.compile(r"_(\d{3})$")


class ExportKind(str, Enum):
    PHOTO_PNG = "photo_png"
    PHOTO_JPEG = "photo_jpeg"
    MOTION = "motion"


def default_export_dir() -> str:
    videos = Path.home() / "Videos"
    if videos.is_dir():
        return str(videos)
    return str(Path.home() / "Pictures")


def is_enhanced_export(enhance_mode: EnhanceMode) -> bool:
    return resolve_export_enhance_mode(enhance_mode) != EnhanceMode.OFF


def extension_for_kind(kind: ExportKind) -> str:
    if kind == ExportKind.PHOTO_PNG:
        return ".png"
    return ".jpg"


def format_motion_time_tag(timestamp_ms: int) -> str:
    total_sec = max(0, timestamp_ms) // 1000
    minutes = total_sec // 60
    seconds = total_sec % 60
    millis = max(0, timestamp_ms) % 1000
    return f"{minutes:02d}m{seconds:02d}s{millis:03d}"


def build_export_stem(
    video_path: str,
    timestamp_ms: int,
    kind: ExportKind,
    enhance_mode: EnhanceMode,
    *,
    lut_active: bool = False,
) -> str:
    """不含扩展名与序号后缀的文件名主干。"""
    stem = Path(video_path).stem or "video"
    tag = ""
    if is_enhanced_export(enhance_mode):
        tag += ENHANCE_SUFFIX
    if lut_active:
        tag += LUT_SUFFIX
    if kind == ExportKind.MOTION:
        return f"MVIMG_{stem}_{format_motion_time_tag(timestamp_ms)}{tag}"
    return f"{stem}_{timestamp_ms}ms{tag}"


def format_export_filename(stem: str, ext: str, seq: int) -> str:
    if seq <= 1:
        return f"{stem}{ext}"
    return f"{stem}_{seq:03d}{ext}"


def parse_export_sequence(filename: str, stem: str, ext: str) -> int | None:
    name = Path(filename).name
    if name == f"{stem}{ext}":
        return 1
    match = re.fullmatch(re.escape(stem) + r"_(\d{3})" + re.escape(ext), name)
    if match:
        return int(match.group(1))
    return None


def next_export_sequence(
    export_dir: Path,
    stem: str,
    ext: str,
    *,
    reserved: set[str] | None = None,
) -> int:
    used: set[int] = set()
    if export_dir.is_dir():
        plain = export_dir / f"{stem}{ext}"
        if plain.is_file():
            used.add(1)
        for path in export_dir.glob(f"{stem}_*{ext}"):
            seq = parse_export_sequence(path.name, stem, ext)
            if seq is not None:
                used.add(seq)
    for name in reserved or ():
        seq = parse_export_sequence(name, stem, ext)
        if seq is not None:
            used.add(seq)
    seq = 1
    while seq in used:
        seq += 1
    return seq


class ExportNameAllocator:
    """会话内预留已分配文件名，配合磁盘扫描避免重复导出冲突。"""

    def __init__(self) -> None:
        self._reserved: set[str] = set()

    def reset(self) -> None:
        self._reserved.clear()

    def peek_next(
        self,
        export_dir: str | Path,
        video_path: str,
        timestamp_ms: int,
        kind: ExportKind,
        enhance_mode: EnhanceMode,
        *,
        lut_active: bool = False,
    ) -> tuple[str, int]:
        directory = Path(export_dir)
        stem = build_export_stem(
            video_path, timestamp_ms, kind, enhance_mode, lut_active=lut_active
        )
        ext = extension_for_kind(kind)
        seq = next_export_sequence(directory, stem, ext, reserved=self._reserved)
        return format_export_filename(stem, ext, seq), seq

    def reserve(self, filename: str) -> None:
        self._reserved.add(Path(filename).name)

    def release(self, filename: str) -> None:
        self._reserved.discard(Path(filename).name)


def build_default_export_filename(
    video_path: str,
    timestamp_ms: int,
    kind: ExportKind,
    enhance_mode: EnhanceMode,
    *,
    export_dir: str | Path | None = None,
    allocator: ExportNameAllocator | None = None,
    lut_active: bool = False,
) -> str:
    directory = Path(export_dir or default_export_dir())
    if allocator is not None:
        name, _ = allocator.peek_next(
            directory,
            video_path,
            timestamp_ms,
            kind,
            enhance_mode,
            lut_active=lut_active,
        )
        return name
    stem = build_export_stem(
        video_path, timestamp_ms, kind, enhance_mode, lut_active=lut_active
    )
    ext = extension_for_kind(kind)
    seq = next_export_sequence(directory, stem, ext)
    return format_export_filename(stem, ext, seq)


def build_motion_photo_filename(
    video_path: str,
    timestamp_ms: int,
    enhance_mode: EnhanceMode = EnhanceMode.OFF,
    *,
    export_dir: str | Path | None = None,
    allocator: ExportNameAllocator | None = None,
    lut_active: bool = False,
) -> str:
    return build_default_export_filename(
        video_path,
        timestamp_ms,
        ExportKind.MOTION,
        enhance_mode,
        export_dir=export_dir,
        allocator=allocator,
        lut_active=lut_active,
    )
