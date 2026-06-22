"""LUT 服务单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.lut_service import (
    LUT_DISABLED,
    LutConfig,
    build_lut_vf,
    describe_lut,
    is_valid_cube_file,
)
from app.services.lut_motion_export import should_apply_lut_to_motion_video
from app.services.lut_presets import LutPreset, write_cube_file
from app.services.quality_enhance_service import EnhanceMode

_SAMPLE_CUBE = """TITLE "test"
LUT_3D_SIZE 2
0 0 0
1 1 1
0.5 0.5 0.5
1 0 0
0 1 0
0 0 1
0.2 0.2 0.2
0.8 0.8 0.8
"""


class TestLutService(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".cube", prefix="lut_test_", delete=False
        )
        self._tmp.write(_SAMPLE_CUBE.encode("utf-8"))
        self._tmp.close()
        self.cube_path = self._tmp.name

    def tearDown(self) -> None:
        Path(self.cube_path).unlink(missing_ok=True)

    def _cfg(self, strength: int = 100) -> LutConfig:
        return LutConfig(enabled=True, lut_path=self.cube_path, strength=strength)

    def test_disabled_config(self) -> None:
        self.assertFalse(LUT_DISABLED.active)
        self.assertIn("关闭", describe_lut(LUT_DISABLED))

    def test_strength_zero_inactive(self) -> None:
        cfg = LutConfig(enabled=True, lut_path=self.cube_path, strength=0)
        self.assertFalse(cfg.active)

    def test_stack_layers(self) -> None:
        second = tempfile.NamedTemporaryFile(
            suffix=".cube", prefix="lut_test2_", delete=False
        )
        second.write(_SAMPLE_CUBE.encode("utf-8"))
        second.close()
        self.addCleanup(lambda: Path(second.name).unlink(missing_ok=True))
        cfg = LutConfig(
            enabled=True,
            lut_path=self.cube_path,
            strength=100,
            stack_lut_path=second.name,
            stack_strength=70,
        )
        self.assertEqual(len(cfg.active_layers()), 2)
        vf = build_lut_vf(cfg)
        self.assertEqual(vf.count("lut3d"), 2)
        self.assertIn("blend=all_opacity=0.7000", vf)
        self.assertIn(" + ", describe_lut(cfg))

    def test_stack_skips_duplicate_lut(self) -> None:
        cfg = LutConfig(
            enabled=True,
            lut_path=self.cube_path,
            strength=100,
            stack_lut_path=self.cube_path,
            stack_strength=80,
        )
        self.assertEqual(len(cfg.active_layers()), 1)

    def test_build_vf_full_strength(self) -> None:
        vf = build_lut_vf(self._cfg(100))
        self.assertIn("lut3d=file=", vf)
        self.assertNotIn("blend", vf)

    def test_build_vf_escapes_windows_drive_colon(self) -> None:
        vf = build_lut_vf(self._cfg(100))
        resolved = str(Path(self.cube_path).resolve()).replace("\\", "/")
        if len(resolved) >= 2 and resolved[1] == ":":
            escaped = f"{resolved[0]}\\:{resolved[2:]}"
            self.assertIn(escaped, vf)

    def test_build_vf_partial_strength(self) -> None:
        vf = build_lut_vf(self._cfg(50))
        self.assertIn("blend=all_opacity=0.5000", vf)

    def test_invalid_cube(self) -> None:
        self.assertFalse(is_valid_cube_file("main.py"))

    def test_cover_tier_skips_video_lut(self) -> None:
        self.assertFalse(
            should_apply_lut_to_motion_video(
                self._cfg(), EnhanceMode.REALESRGAN_COVER
            )
        )

    def test_off_enhance_applies_video_lut(self) -> None:
        self.assertTrue(
            should_apply_lut_to_motion_video(self._cfg(), EnhanceMode.OFF)
        )

    def test_builtin_presets_generated(self) -> None:
        from app.services.lut_service import list_builtin_luts, preset_label_for_path

        luts = list_builtin_luts()
        self.assertGreaterEqual(len(luts), 7)
        self.assertEqual(preset_label_for_path(luts[0]), "柔肤人像")

    def test_cube_axis_order_matches_ffmpeg(self) -> None:
        """错误轴顺序会把红通道映射成蓝（预览发蓝）。"""
        from app.services.lut_service import apply_lut_to_png
        from app.services.lut_presets import LutPreset
        from app.services.subprocess_util import run_text
        from app.services.tool_paths import resolve_tool

        def identity(_r: float, _g: float, _b: float) -> tuple[float, float, float]:
            return _r, _g, _b

        preset = LutPreset("identity.cube", "identity", "Identity", "test", identity)
        cube = Path(self.cube_path).with_name("identity_axis.cube")
        write_cube_file(cube, preset, size=3)

        png = Path(self.cube_path).with_suffix(".png")
        ff = resolve_tool("ffmpeg")
        result = run_text(
            [
                ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=32x32:r=8",
                "-pix_fmt",
                "rgb24",
                "-frames:v",
                "1",
                str(png),
            ]
        )
        self.assertEqual(result.returncode, 0)

        cfg = LutConfig(enabled=True, lut_path=str(cube), strength=100)
        apply_lut_to_png(str(png), cfg)

        from PIL import Image

        with Image.open(png) as img:
            r, g, b = img.convert("RGB").getpixel((8, 8))
        self.assertGreater(r, 200, f"identity LUT should keep red, got RGB=({r},{g},{b})")
        self.assertLess(b, 30)


if __name__ == "__main__":
    unittest.main()
