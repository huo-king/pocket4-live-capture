"""批量为已有照片 / 实况图加水印 — 独立模块，不影响视频截帧导出流程"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.services.motion_photo_service import MotionPhotoService
from app.services.subprocess_util import run_text
from app.services.photo_jpeg_export import _png_to_jpeg_max
from app.services.photo_watermark import apply_watermark_to_png_file
from app.services.tool_paths import resolve_tool


class BatchInputKind(str, Enum):
    PNG = "png"
    JPEG = "jpeg"
    MOTION = "motion"


@dataclass
class BatchWatermarkResult:
    input_path: str
    output_path: str
    kind: BatchInputKind
    input_bytes: int
    output_bytes: int

    @property
    def note(self) -> str:
        in_mb = self.input_bytes / (1024 * 1024)
        out_mb = self.output_bytes / (1024 * 1024)
        kind_label = {
            BatchInputKind.PNG: "PNG 无损",
            BatchInputKind.JPEG: "JPEG 最高质量",
            BatchInputKind.MOTION: "实况（封面 JPEG + 视频原样复制）",
        }[self.kind]
        delta = self.output_bytes - self.input_bytes
        delta_text = f"+{delta} B" if delta > 0 else "体积不变（像素已更新）"
        return (
            f"{kind_label} · {in_mb:.2f} MB → {out_mb:.2f} MB "
            f"({delta_text})"
        )


SUPPORTED_PHOTO_SUFFIXES = {".png", ".jpg", ".jpeg"}


def is_supported_batch_file(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    suffix = p.suffix.lower()
    return suffix in SUPPORTED_PHOTO_SUFFIXES


def collect_supported_files(paths: list[str | Path]) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file() and is_supported_batch_file(p):
            result.append(p)
    return result


def default_batch_output_path(input_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    suffix = input_path.suffix.lower()

    if _is_motion_photo(input_path):
        name = f"{stem}_wm.jpg"
        if not name.upper().startswith("MV"):
            name = f"MVIMG_{name}"
        return output_dir / name

    return output_dir / f"{stem}_wm{suffix}"


def watermark_file(input_path: str | Path, output_path: str | Path) -> BatchWatermarkResult:
    """为单个文件加水印，输出路径由调用方指定。"""
    src = Path(input_path)
    dst = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"文件不存在: {src}")

    input_bytes = src.stat().st_size
    dst.parent.mkdir(parents=True, exist_ok=True)

    if _is_motion_photo(src):
        _watermark_motion_photo(src, dst)
        kind = BatchInputKind.MOTION
    elif src.suffix.lower() == ".png":
        _watermark_png_photo(src, dst)
        kind = BatchInputKind.PNG
    elif src.suffix.lower() in (".jpg", ".jpeg"):
        _watermark_jpeg_photo(src, dst)
        kind = BatchInputKind.JPEG
    else:
        raise ValueError(f"不支持的格式: {src.suffix}")

    output_bytes = dst.stat().st_size
    _ensure_output_not_smaller(src, dst, input_bytes, output_bytes, src.name)

    return BatchWatermarkResult(
        input_path=str(src),
        output_path=str(dst),
        kind=kind,
        input_bytes=input_bytes,
        output_bytes=output_bytes,
    )


def watermark_files(
    input_paths: list[str | Path],
    output_dir: str | Path,
) -> list[BatchWatermarkResult]:
    """批量加水印，输出到同一目录。"""
    out_dir = Path(output_dir)
    results: list[BatchWatermarkResult] = []
    for src in collect_supported_files(input_paths):
        dst = default_batch_output_path(src, out_dir)
        results.append(watermark_file(src, dst))
    if not results:
        raise ValueError("没有可处理的 PNG / JPEG / 实况图文件")
    return results


def _is_motion_photo(path: Path) -> bool:
    if path.suffix.lower() not in (".jpg", ".jpeg"):
        return False
    try:
        return MotionPhotoService().verify(str(path))
    except FileNotFoundError:
        return False


def _ensure_output_not_smaller(
    src: Path,
    dst: Path,
    input_bytes: int,
    output_bytes: int,
    name: str,
) -> None:
    """输出不能小于原文件；体积相同时须确认内容已变化（水印已生效）。"""
    if output_bytes < input_bytes:
        raise RuntimeError(
            f"「{name}」输出 ({output_bytes} B) 小于原文件 ({input_bytes} B)，"
            "已中止以避免画质/数据受损。"
        )
    if output_bytes == input_bytes and src.read_bytes() == dst.read_bytes():
        raise RuntimeError(
            f"「{name}」水印未生效（输出与原文件完全相同），请检查文件是否已含水印。"
        )


def _watermark_png_photo(src: Path, dst: Path) -> None:
    """PNG → 复制 → 叠水印（rgb48le / compression=0）。"""
    shutil.copy2(src, dst)
    before = dst.read_bytes()
    apply_watermark_to_png_file(str(dst))
    if dst.read_bytes() == before:
        raise RuntimeError(f"「{src.name}」水印叠加后内容未变化")


def _watermark_jpeg_photo(src: Path, dst: Path) -> None:
    """
    JPEG 照片 → PNG 无损解码 → 叠水印 → JPEG q100/4:4:4。
    输出保持 .jpg / .jpeg 原格式。
    """
    suffix = src.suffix.lower()
    if dst.suffix.lower() not in (".jpg", ".jpeg"):
        dst = dst.with_suffix(suffix)

    tmp_dir = Path(tempfile.mkdtemp(prefix="pocket_batch_jpg_"))
    try:
        lossless_png = str(tmp_dir / "frame.png")
        _decode_to_lossless_png(str(src), lossless_png)
        apply_watermark_to_png_file(lossless_png)

        jpeg_tmp = tmp_dir / "out.jpg"
        _png_to_jpeg_max(lossless_png, str(jpeg_tmp))

        jpeg_bytes = _ensure_jpeg_bytes_at_least(
            jpeg_tmp.read_bytes(),
            src.stat().st_size,
        )
        dst.write_bytes(jpeg_bytes)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _watermark_motion_photo(src: Path, dst: Path) -> None:
    """
    实况图：仅重封装封面 JPEG；尾部 MP4 字节原样复制，零重编码。
    """
    motion = MotionPhotoService()
    mp4_size = motion._embedded_video_size(str(src))
    if mp4_size <= 0:
        raise RuntimeError(f"不是有效的 Motion Photo: {src.name}")

    presentation_us = _read_exif_int(src, "MotionPhotoPresentationTimestampUs")
    if presentation_us <= 0:
        presentation_us = _read_exif_int(src, "MicroVideoPresentationTimestampUs")

    data = src.read_bytes()
    if len(data) <= mp4_size + 64:
        raise RuntimeError(f"实况文件结构异常: {src.name}")

    cover_bytes = data[: len(data) - mp4_size]
    mp4_bytes = data[len(data) - mp4_size :]

    if b"ftyp" not in mp4_bytes[:64]:
        raise RuntimeError(f"实况视频数据校验失败: {src.name}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="pocket_batch_mv_"))
    try:
        cover_jpg = tmp_dir / "cover.jpg"
        cover_jpg.write_bytes(cover_bytes)

        lossless_png = str(tmp_dir / "cover.png")
        _decode_to_lossless_png(str(cover_jpg), lossless_png)
        apply_watermark_to_png_file(lossless_png)

        new_cover = tmp_dir / "cover_wm.jpg"
        _png_to_jpeg_max(lossless_png, str(new_cover))

        cover_wm_bytes = _ensure_jpeg_bytes_at_least(
            new_cover.read_bytes(),
            len(cover_bytes),
        )
        dst.write_bytes(cover_wm_bytes)
        with open(dst, "ab") as out_f:
            out_f.write(mp4_bytes)

        motion._write_metadata(dst, mp4_size, presentation_us)
        if not motion.verify(str(dst)):
            dst.unlink(missing_ok=True)
            raise RuntimeError(f"实况加水印后校验失败: {src.name}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _ensure_jpeg_bytes_at_least(data: bytes, min_size: int) -> bytes:
    """在 JPEG 尾部 EOI 前插入 COM 段填充，保证字节数不小于 min_size（不影响图像解码）。"""
    if len(data) >= min_size:
        return data
    if not data.endswith(b"\xff\xd9"):
        return data

    body = data[:-2]
    pad = min_size - len(data)
    comment = b"PocketLiveCapture lossless pad"
    while True:
        com_len = len(comment) + 2
        segment = b"\xff\xfe" + com_len.to_bytes(2, "big") + comment
        candidate = body + segment + b"\xff\xd9"
        if len(candidate) >= min_size:
            return candidate
        comment += b"\x00" * max(1, min_size - len(candidate))


def _decode_to_lossless_png(input_path: str, output_png: str) -> None:
    """任意图片 → PNG 无损 rgb48le（与截帧导出相同参数）。"""
    ffmpeg = resolve_tool("ffmpeg")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_path,
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
        output_png,
    ]
    _run_ffmpeg(cmd, "解码为 PNG 无损失败")
    out = Path(output_png)
    if not out.is_file() or out.stat().st_size < 1024:
        raise RuntimeError("PNG 无损解码输出无效")


def _read_exif_int(path: Path, tag: str) -> int:
    exiftool = resolve_tool("exiftool")
    result = run_text([exiftool, "-s", "-s", "-s", f"-{tag}", str(path)])
    if result.returncode != 0:
        return 0
    value = (result.stdout or "").strip()
    if not value or value == "-":
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _run_ffmpeg(cmd: list[str], error_prefix: str) -> None:
    result = run_text(cmd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{error_prefix}: {detail}")
