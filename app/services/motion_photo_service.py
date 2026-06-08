"""Motion Photo 封装 — Google + 小米相册兼容格式"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.services.subprocess_util import run_text
from app.services.tool_paths import resolve_tool, _bundle_root


class MotionPhotoService:
    def create(
        self,
        frame_jpg: str,
        clip_mp4: str,
        output_jpg: str,
        timestamp_us: int,
    ) -> str:
        output = Path(output_jpg)
        clip = Path(clip_mp4)

        if not output.name.startswith("MV"):
            raise ValueError("Motion Photo 文件名必须以 MV 开头（如 MVIMG_xxx.jpg）")
        if not clip.is_file():
            raise FileNotFoundError(f"视频片段不存在: {clip}")

        mp4_size = clip.stat().st_size
        if mp4_size <= 0:
            raise RuntimeError("视频片段为空，无法生成实况图")

        # 小米社区方案：先拼接 JPEG+MP4，再写入 XMP/EXIF（避免元数据写入破坏尾部视频）
        shutil.copy2(frame_jpg, output)
        with open(output, "ab") as out_file, open(clip, "rb") as video_file:
            shutil.copyfileobj(video_file, out_file)

        self._write_metadata(output, mp4_size, timestamp_us)

        if not self.verify(str(output)):
            output.unlink(missing_ok=True)
            raise RuntimeError(
                "Motion Photo 校验失败：嵌入视频或元数据异常。"
                "请确认使用 USB 原文件传输，勿经微信/QQ（会剥离实况数据）。"
            )

        return str(output)

    def _write_metadata(self, media: Path, mp4_size: int, timestamp_us: int) -> None:
        exiftool = resolve_tool("exiftool")
        mi_config = _bundle_root() / "tools" / "mi.config"
        directory = (
            "[{Item={Length=0,Mime=image/jpeg,Padding=0,Semantic=Primary}},"
            f"{{Item={{Length={mp4_size},Mime=video/mp4,Padding=0,Semantic=MotionPhoto}}}}]"
        )

        cmd = [exiftool]
        if mi_config.is_file():
            cmd.extend(["-config", str(mi_config), "-MVIMG=1"])

        cmd.extend(
            [
                "-n",
                "-overwrite_original",
                "-ignoreMinorErrors",
                "-XMP-GCamera:MotionPhoto=1",
                "-XMP-GCamera:MotionPhotoVersion=1",
                f"-XMP-GCamera:MotionPhotoPresentationTimestampUs={timestamp_us}",
                "-XMP-GCamera:MicroVideo=1",
                "-XMP-GCamera:MicroVideoVersion=1",
                f"-XMP-GCamera:MicroVideoOffset={mp4_size}",
                f"-XMP-GCamera:MicroVideoPresentationTimestampUs={timestamp_us}",
                f"-XMP-GContainer:ContainerDirectory={directory}",
                str(media),
            ]
        )

        result = run_text(cmd)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"写入 Motion Photo 元数据失败: {detail}")

        after_size = media.stat().st_size
        before_video = after_size - mp4_size
        if after_size <= before_video:
            raise RuntimeError("元数据写入后视频数据丢失，请检查 ExifTool 配置")

    def verify(self, output_jpg: str) -> bool:
        path = Path(output_jpg)
        if not path.is_file():
            return False

        mp4_size = self._embedded_video_size(output_jpg)
        if mp4_size <= 0:
            return False

        data = path.read_bytes()
        if len(data) <= mp4_size + 64:
            return False

        tail = data[-mp4_size:]
        if b"ftyp" not in tail[:64]:
            return False

        try:
            exiftool = resolve_tool("exiftool")
        except FileNotFoundError:
            return True

        result = run_text([exiftool, "-G1", "-s", output_jpg])
        if result.returncode != 0:
            return False

        text = result.stdout
        has_motion = (
            "MotionPhoto" in text
            and re.search(r"MotionPhoto\s*:\s*1", text) is not None
        )
        has_micro = "MicroVideo" in text and re.search(r"MicroVideo\s*:\s*1", text) is not None
        return has_motion and has_micro

    @staticmethod
    def _embedded_video_size(output_jpg: str) -> int:
        try:
            exiftool = resolve_tool("exiftool")
        except FileNotFoundError:
            return 0

        result = run_text(
            [exiftool, "-s", "-s", "-s", "-MicroVideoOffset", output_jpg]
        )
        if result.returncode != 0:
            return 0

        value = result.stdout.strip()
        if not value or value == "-":
            return 0
        try:
            return int(value)
        except ValueError:
            return 0
