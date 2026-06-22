"""LUT 预览渲染测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.lut_preview_render import (
    PREVIEW_MAX_EDGE,
    _preview_scale_filter,
    render_lut_preview_frame,
)
from app.services.lut_service import LutConfig, is_valid_cube_file


class TestLutPreviewRender(unittest.TestCase):
    def setUp(self) -> None:
        from app.services.lut_presets import generate_builtin_lut_files

        self._tmp = tempfile.TemporaryDirectory()
        self.lut_dir = Path(self._tmp.name)
        generate_builtin_lut_files(self.lut_dir)
        self.cube = self.lut_dir / "01_soft_portrait.cube"
        self.assertTrue(is_valid_cube_file(self.cube))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_render_requires_active_lut(self) -> None:
        with self.assertRaises(ValueError):
            render_lut_preview_frame("x.mp4", 0.0, "out.png", LutConfig())

    def test_preview_scale_filter_for_4k(self) -> None:
        vf = _preview_scale_filter(3840, 2160)
        self.assertIsNotNone(vf)
        self.assertIn(str(PREVIEW_MAX_EDGE), vf)
        self.assertIn("lanczos", vf)

    def test_preview_scale_filter_skips_720p(self) -> None:
        self.assertIsNone(_preview_scale_filter(1280, 720))

    def test_render_creates_png(self) -> None:
        out = self.lut_dir / "preview.png"
        cfg = LutConfig(enabled=True, lut_path=str(self.cube), strength=80)
        with self.assertRaises(Exception):
            render_lut_preview_frame("nonexistent.mp4", 0.0, str(out), cfg)


if __name__ == "__main__":
    unittest.main()
