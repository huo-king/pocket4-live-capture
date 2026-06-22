"""导出文件名：普通/增强后缀区分与序号递增。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.export_naming import (
    ENHANCE_SUFFIX,
    ExportKind,
    ExportNameAllocator,
    build_default_export_filename,
    build_export_stem,
    build_motion_photo_filename,
    next_export_sequence,
)
from app.services.quality_enhance_service import EnhanceMode


class TestExportNaming(unittest.TestCase):
    def test_stem_differs_for_enhanced(self) -> None:
        video = "clip.MP4"
        ts = 79120
        normal = build_export_stem(video, ts, ExportKind.PHOTO_PNG, EnhanceMode.OFF)
        enhanced = build_export_stem(
            video, ts, ExportKind.PHOTO_PNG, EnhanceMode.REALESRGAN_COVER
        )
        self.assertNotEqual(normal, enhanced)
        self.assertIn(ENHANCE_SUFFIX, enhanced)
        self.assertNotIn(ENHANCE_SUFFIX, normal)

    def test_motion_filename_prefix(self) -> None:
        name = build_motion_photo_filename("a.MP4", 79120, EnhanceMode.OFF)
        self.assertTrue(name.startswith("MVIMG_"))
        self.assertTrue(name.endswith(".jpg"))

    def test_sequence_increments_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            stem = build_export_stem("v.MP4", 1000, ExportKind.PHOTO_PNG, EnhanceMode.OFF)
            ext = ".png"
            (export_dir / f"{stem}{ext}").write_bytes(b"x")
            self.assertEqual(next_export_sequence(export_dir, stem, ext), 2)
            (export_dir / f"{stem}_002{ext}").write_bytes(b"x")
            self.assertEqual(next_export_sequence(export_dir, stem, ext), 3)

    def test_allocator_reserves_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            allocator = ExportNameAllocator()
            name1, seq1 = allocator.peek_next(
                export_dir, "v.MP4", 1000, ExportKind.PHOTO_JPEG, EnhanceMode.OFF
            )
            allocator.reserve(name1)
            name2, seq2 = allocator.peek_next(
                export_dir, "v.MP4", 1000, ExportKind.PHOTO_JPEG, EnhanceMode.OFF
            )
            self.assertEqual(seq1, 1)
            self.assertEqual(seq2, 2)
            self.assertNotEqual(name1, name2)

    def test_enhanced_and_normal_do_not_share_counter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            normal = build_default_export_filename(
                "v.MP4", 5000, ExportKind.PHOTO_PNG, EnhanceMode.OFF, export_dir=export_dir
            )
            enhanced = build_default_export_filename(
                "v.MP4",
                5000,
                ExportKind.PHOTO_PNG,
                EnhanceMode.REALESRGAN_COVER,
                export_dir=export_dir,
            )
            self.assertNotEqual(normal, enhanced)
            (export_dir / normal).write_bytes(b"n")
            (export_dir / enhanced).write_bytes(b"e")
            next_normal = build_default_export_filename(
                "v.MP4", 5000, ExportKind.PHOTO_PNG, EnhanceMode.OFF, export_dir=export_dir
            )
            next_enhanced = build_default_export_filename(
                "v.MP4",
                5000,
                ExportKind.PHOTO_PNG,
                EnhanceMode.REALESRGAN_COVER,
                export_dir=export_dir,
            )
            self.assertTrue(next_normal.endswith("_002.png"))
            self.assertTrue(next_enhanced.endswith("_002.png"))


if __name__ == "__main__":
    unittest.main()
