"""DJI LUT 下载服务单元测试。"""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.dji_lut_download import (
    download_dji_lut,
    get_dji_lut_catalog,
    get_dji_lut_catalog_by_category,
    is_already_downloaded,
)
from app.services.lut_service import is_valid_cube_file

_SAMPLE_CUBE = b"""TITLE "test"
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


class TestDjiLutDownload(unittest.TestCase):
    def test_catalog_has_expected_groups(self) -> None:
        grouped = get_dji_lut_catalog_by_category()
        self.assertIn("pocket", grouped)
        self.assertIn("action", grouped)
        self.assertIn("drone", grouped)
        self.assertGreaterEqual(len(grouped["pocket"]), 4)
        self.assertGreaterEqual(len(get_dji_lut_catalog()), 20)

    def test_download_skips_valid_existing_file(self) -> None:
        entry = get_dji_lut_catalog()[0]
        with tempfile.TemporaryDirectory() as tmp:
            lut_dir = Path(tmp)
            dest = lut_dir / entry.output_filename
            dest.write_bytes(_SAMPLE_CUBE)

            with patch("app.services.dji_lut_download.user_lut_dir", return_value=lut_dir):
                self.assertTrue(is_already_downloaded(entry))
                result = download_dji_lut(entry, opener=self._fail_if_called)
                self.assertEqual(result, dest)

    def test_download_writes_and_validates(self) -> None:
        entry = get_dji_lut_catalog()[0]
        with tempfile.TemporaryDirectory() as tmp:
            lut_dir = Path(tmp)

            def fake_open(_request, timeout=120):
                return io.BytesIO(_SAMPLE_CUBE)

            with patch("app.services.dji_lut_download.user_lut_dir", return_value=lut_dir):
                path = download_dji_lut(entry, opener=fake_open)
                self.assertTrue(path.is_file())
                self.assertTrue(is_valid_cube_file(path))

    def test_download_rejects_invalid_payload(self) -> None:
        entry = get_dji_lut_catalog()[0]
        with tempfile.TemporaryDirectory() as tmp:
            lut_dir = Path(tmp)

            def fake_open(_request, timeout=120):
                return io.BytesIO(b"not a cube")

            with patch("app.services.dji_lut_download.user_lut_dir", return_value=lut_dir):
                with self.assertRaises(RuntimeError):
                    download_dji_lut(entry, opener=fake_open)

    @staticmethod
    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("urlopen should not be called when file already exists")


if __name__ == "__main__":
    unittest.main()
