"""画质增强关闭时，导出链路不得调用任何增强处理。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.quality_enhance_service import EnhanceMode, resolve_enhance_mode


class TestEnhanceOffGuard(unittest.TestCase):
    def test_coerce_mode_from_combo_string(self) -> None:
        from app.services.quality_enhance_service import coerce_enhance_mode

        self.assertEqual(
            coerce_enhance_mode("ffmpeg_light"),
            EnhanceMode.FFMPEG_LIGHT,
        )
        self.assertEqual(
            coerce_enhance_mode(EnhanceMode.REALESRGAN_COVER),
            EnhanceMode.REALESRGAN_COVER,
        )
        self.assertIsNone(coerce_enhance_mode("invalid"))

    def test_resolve_off_when_disabled(self) -> None:
        self.assertEqual(resolve_enhance_mode(False), EnhanceMode.OFF)

    def test_extract_uses_fast_seek(self) -> None:
        source = Path("app/services/photo_png_export.py").read_text(encoding="utf-8")
        self.assertIn("_SEEK_MARGIN_SEC", source)
        # 粗定位 -ss 必须在 -i 之前
        idx_i = source.index('"-i",\n        video_path,', source.index("def extract_lossless_png"))
        idx_ss_coarse = source.rfind('"-ss",', 0, idx_i)
        self.assertGreater(idx_ss_coarse, 0)

    def test_stream_copy_fast_seek(self) -> None:
        source = Path("app/services/ffmpeg_service.py").read_text(encoding="utf-8")
        block = source[source.index("def _stream_copy") : source.index("def _validate_clip")]
        self.assertIn("accurate: bool = False", block)
        self.assertIn("if accurate:", block)
        self.assertIn('f"{start_sec:.6f}",\n                "-i",\n                video_path,', block)

    def test_clip_extract_retries_accurate(self) -> None:
        source = Path("app/services/ffmpeg_service.py").read_text(encoding="utf-8")
        self.assertIn("for accurate in (False, True):", source)

    def test_tier_options_count(self) -> None:
        from app.services.quality_enhance_service import ENHANCE_TIER_OPTIONS

        self.assertEqual(len(ENHANCE_TIER_OPTIONS), 3)

    @patch("app.services.photo_png_export.enhance_png_file")
    def test_process_export_png_skips_enhance_when_off(self, mock_enhance: MagicMock) -> None:
        from app.services.photo_png_export import process_export_png

        process_export_png("fake.png", apply_watermark=False, enhance_mode=EnhanceMode.OFF)
        mock_enhance.assert_not_called()

    @patch("app.services.photo_png_export.enhance_png_file")
    @patch("app.services.photo_png_export.apply_watermark_to_png_file")
    def test_process_export_png_watermark_only_no_enhance(
        self, mock_wm: MagicMock, mock_enhance: MagicMock
    ) -> None:
        from app.services.photo_png_export import process_export_png

        process_export_png("fake.png", apply_watermark=True, enhance_mode=EnhanceMode.OFF)
        mock_enhance.assert_not_called()
        mock_wm.assert_called_once_with("fake.png")

    @patch("app.services.quality_enhance_service._enhance_realesrgan_ncnn")
    @patch("app.services.quality_enhance_service._enhance_ffmpeg_light")
    def test_enhance_png_off_is_noop(
        self, mock_ff: MagicMock, mock_sr: MagicMock
    ) -> None:
        from app.services.quality_enhance_service import enhance_png_file

        out, note = enhance_png_file("in.png", mode=EnhanceMode.OFF)
        self.assertEqual(out, "in.png")
        self.assertIn("关闭", note)
        mock_ff.assert_not_called()
        mock_sr.assert_not_called()

    def test_export_worker_off_gate_in_source(self) -> None:
        """export_worker 仅在 should_enhance_motion_video 为真时调用 enhance_video_clip。"""
        from pathlib import Path

        source = Path("app/services/export_worker.py").read_text(encoding="utf-8")
        marker = "if self.enhance_mode != EnhanceMode.OFF and should_enhance_motion_video("
        gate = source.index(marker)
        enhance_idx = source.index("enhance_video_clip(", gate)
        else_idx = source.index("else:", enhance_idx)
        self.assertLess(enhance_idx, else_idx)

    def test_realesrgan_motion_video_off_by_default(self) -> None:
        from app.services.quality_enhance_service import (
            EnhanceMode,
            should_enhance_motion_video,
        )

        self.assertFalse(should_enhance_motion_video(EnhanceMode.REALESRGAN_COVER))
        self.assertTrue(should_enhance_motion_video(EnhanceMode.REALESRGAN_FULL))
        self.assertTrue(should_enhance_motion_video(EnhanceMode.FFMPEG_LIGHT))

    def test_realesrgan_uses_model_native_scale(self) -> None:
        """2× 目标仍须对 x4plus 传 -s 4，避免 ncnn tile 错位 bug。"""
        from pathlib import Path

        from app.services.quality_enhance_service import REALESRGAN_MODEL_SCALE

        source = Path("app/services/quality_enhance_service.py").read_text(encoding="utf-8")
        self.assertIn('str(REALESRGAN_MODEL_SCALE)', source)
        self.assertNotIn('str(scale),\n        "-f",', source)


if __name__ == "__main__":
    unittest.main()
