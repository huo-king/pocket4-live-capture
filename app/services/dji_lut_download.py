"""DJI 官方色彩还原 LUT — 从 DJI CDN 下载到用户 LUT 目录。"""

from __future__ import annotations

import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.services.lut_service import user_lut_dir

CDN = "https://terra-1-g.djicdn.com/851d20f7b9f64838a34cd02351370894"
CDN_OP3 = "https://www-dl.djicdn.com/5e45168b46b342d5b88f72c458ba6e79"

CATEGORY_LABELS = {
    "pocket": "Pocket 系列",
    "action": "Action 系列",
    "drone": "无人机系列",
}


@dataclass(frozen=True)
class DjiLutEntry:
    display_name: str
    device: str
    category: str
    log_type: str
    variant: str
    cdn_url: str
    output_filename: str
    description: str = ""


def _entry(
    display_name: str,
    device: str,
    category: str,
    log_type: str,
    variant: str,
    cdn_url: str,
    output_filename: str,
    *,
    description: str = "",
) -> DjiLutEntry:
    return DjiLutEntry(
        display_name=display_name,
        device=device,
        category=category,
        log_type=log_type,
        variant=variant,
        cdn_url=cdn_url,
        output_filename=output_filename,
        description=description or f"{variant} · 33³",
    )


_DJI_LUT_CATALOG: tuple[DjiLutEntry, ...] = (
    # Pocket
    _entry(
        "Pocket 4 D-Log → Rec.709 标准",
        "Osmo Pocket 4",
        "pocket",
        "D-Log",
        "standard",
        f"{CDN}/HG214%20Lut/DJI%20OSMO%20Pocket%204%20D-Log%20to%20Rec.709%20V1.0.cube",
        "DJI_Pocket4_D-Log_to_Rec709.cube",
    ),
    _entry(
        "Pocket 4 D-Log → Rec.709 鲜艳",
        "Osmo Pocket 4",
        "pocket",
        "D-Log",
        "vivid",
        f"{CDN}/HG214%20Lut/DJI%20OSMO%20Pocket%204%20D-Log%20to%20Rec.709%20vivid%20V1.0.cube",
        "DJI_Pocket4_D-Log_to_Rec709_vivid.cube",
    ),
    _entry(
        "Pocket 3 D-Log M → Rec.709",
        "Osmo Pocket 3",
        "pocket",
        "D-Log M",
        "standard",
        f"{CDN_OP3}/OP3%20LUT%E6%96%87%E4%BB%B6%E7%89%B9%E6%AE%8A%E5%A4%84%E7%90%86/DJI%20OSMO%20Pocket%203%20D-Log%20M%20to%20Rec.709%20V1.cube",
        "DJI_Pocket3_D-LogM_to_Rec709.cube",
    ),
    _entry(
        "Pocket 4P D-Log → Rec.709 标准",
        "Osmo Pocket 4P",
        "pocket",
        "D-Log",
        "standard",
        f"{CDN}/HG224%20LUT/DJI%20OSMO%20Pocket%204P%20D-Log%20to%20Rec.709%20V1.0%20size33.cube",
        "DJI_Pocket4P_D-Log_to_Rec709_size33.cube",
    ),
    _entry(
        "Pocket 4P D-Log → Rec.709 鲜艳",
        "Osmo Pocket 4P",
        "pocket",
        "D-Log",
        "vivid",
        f"{CDN}/HG224%20LUT/DJI%20OSMO%20Pocket%204P%20D-Log%20to%20Rec.709%20vivid%20V1.0%20size33.cube",
        "DJI_Pocket4P_D-Log_to_Rec709_vivid_size33.cube",
    ),
    _entry(
        "Pocket 4P D-Log2 → Rec.709 标准",
        "Osmo Pocket 4P",
        "pocket",
        "D-Log2",
        "standard",
        f"{CDN}/HG224%20LUT/DJI%20OSMO%20Pocket%204P%20D-Log2%20to%20Rec.709%20V1.0%20size33.cube",
        "DJI_Pocket4P_D-Log2_to_Rec709_size33.cube",
    ),
    _entry(
        "Pocket 4P D-Log2 → Rec.709 鲜艳",
        "Osmo Pocket 4P",
        "pocket",
        "D-Log2",
        "vivid",
        f"{CDN}/HG224%20LUT/DJI%20OSMO%20Pocket%204P%20D-Log2%20to%20Rec.709%20vivid%20V1.0%20size33.cube",
        "DJI_Pocket4P_D-Log2_to_Rec709_vivid_size33.cube",
    ),
    _entry(
        "Osmo Nano D-Log M → Rec.709 鲜艳",
        "Osmo Nano",
        "pocket",
        "D-Log M",
        "vivid",
        f"{CDN}/OW001%20LUT/DJI%20OSMO%20Osmo%20Nano%20D-Log%20M%20to%20Rec.709%20V1.cube",
        "DJI_Osmo_Nano_D-LogM_to_Rec709_vivid.cube",
    ),
    # Action
    _entry(
        "Action 4 D-Log M → Rec.709 鲜艳",
        "Osmo Action 4",
        "action",
        "D-Log M",
        "vivid",
        f"{CDN}/203/DJI%20OSMO%20Action%204%20D-Log%20M%20to%20Rec.709%20V1.cube",
        "DJI_Action4_D-LogM_to_Rec709_vivid.cube",
    ),
    _entry(
        "Action 5 Pro D-Log M → Rec.709 鲜艳",
        "Osmo Action 5 Pro",
        "action",
        "D-Log M",
        "vivid",
        f"{CDN}/AC204%E8%BD%AF%E4%BB%B6/DJI%20OSMO%20Action%205%20Pro%20D-Log%20M%20to%20Rec.709%20V1.cube",
        "DJI_Action5Pro_D-LogM_to_Rec709_vivid.cube",
    ),
    _entry(
        "Action 6 D-Log M → Rec.709",
        "Osmo Action 6",
        "action",
        "D-Log M",
        "standard",
        f"{CDN}/AC206%20LUT/DJI%20OSMO%20Action%206%20D-LogM%20to%20Rec.709%20LUT-11.17.cube",
        "DJI_Action6_D-LogM_to_Rec709.cube",
    ),
    # Drone
    _entry(
        "Air 3 D-Log M → Rec.709",
        "DJI Air 3",
        "drone",
        "D-Log M",
        "standard",
        f"{CDN}/DJI%20Air%203%20Lut/DJI%20Air%203%20D-Log%20M%20to%20Rec.709%20V1_.cube",
        "DJI_Air3_D-LogM_to_Rec709.cube",
    ),
    _entry(
        "Air 3S D-Log M → Rec.709",
        "DJI Air 3S",
        "drone",
        "D-Log M",
        "standard",
        f"{CDN}/234_lut/DJI%20Air%203S%20%20D-Log%20M%20to%20Rec.709%20V1_.cube",
        "DJI_Air3S_D-LogM_to_Rec709.cube",
    ),
    _entry(
        "Mini 4 Pro D-Log M → Rec.709",
        "DJI Mini 4 Pro",
        "drone",
        "D-Log M",
        "standard",
        f"{CDN}/140%20lut/DJI%20Mini%204%20Pro%20D-Log%20M%20to%20Rec.709%20V1_.cube",
        "DJI_Mini4Pro_D-LogM_to_Rec709.cube",
    ),
    _entry(
        "Mini 5 Pro D-Log M → Rec.709",
        "DJI Mini 5 Pro",
        "drone",
        "D-Log M",
        "standard",
        f"{CDN}/WA150%20LUT/DJI%20Mini%205%20Pro%20D-Log%20M%20to%20Rec.709%20LUT.cube",
        "DJI_Mini5Pro_D-LogM_to_Rec709.cube",
    ),
    _entry(
        "Mavic 3 D-Log → Rec.709 标准",
        "DJI Mavic 3",
        "drone",
        "D-Log",
        "standard",
        f"{CDN}/260%20downloads/DJI%20Mavic%203%20D-Log%20to%20Rec.709%20V1.cube",
        "DJI_Mavic3_D-Log_to_Rec709.cube",
    ),
    _entry(
        "Mavic 3 D-Log → Rec.709 鲜艳",
        "DJI Mavic 3",
        "drone",
        "D-Log",
        "vivid",
        f"{CDN}/mavic%203/DJI%20Mavic%203%20D-Log%20to%20Rec.709%20vivid%20V1.cube",
        "DJI_Mavic3_D-Log_to_Rec709_vivid.cube",
    ),
    _entry(
        "Mavic 4 Pro D-Log → Rec.709 标准",
        "DJI Mavic 4 Pro",
        "drone",
        "D-Log",
        "standard",
        f"{CDN}/WA341%20LUT/DJI%20Mavic%204%20Pro%20D-Log%20to%20Rec.709%20V1.cube",
        "DJI_Mavic4Pro_D-Log_to_Rec709.cube",
    ),
    _entry(
        "Mavic 4 Pro D-Log → Rec.709 鲜艳",
        "DJI Mavic 4 Pro",
        "drone",
        "D-Log",
        "vivid",
        f"{CDN}/WA341%20LUT/DJI%20Mavic%204%20Pro%20D-Log%20to%20Rec.709%20vivid%20V1.cube",
        "DJI_Mavic4Pro_D-Log_to_Rec709_vivid.cube",
    ),
    _entry(
        "Mavic 4 Pro D-Log M → Rec.709",
        "DJI Mavic 4 Pro",
        "drone",
        "D-Log M",
        "standard",
        f"{CDN}/WA341%20LUT/DJI%20Mavic%204%20Pro%20D-Log%20M%20to%20Rec.709%20V1.cube",
        "DJI_Mavic4Pro_D-LogM_to_Rec709.cube",
    ),
    _entry(
        "Avata 2 D-Log M → Rec.709",
        "DJI Avata 2",
        "drone",
        "D-Log M",
        "standard",
        f"{CDN}/avata2%20d-log/DJI%20Avata%202%20D-Log%20M%20to%20Rec.709%20V1_.cube",
        "DJI_Avata2_D-LogM_to_Rec709.cube",
    ),
    _entry(
        "Flip D-Log M → Rec.709",
        "DJI Flip",
        "drone",
        "D-Log M",
        "standard",
        f"{CDN}/141%20LUT/DJI%20Flip%20D-Log%20M%20to%20Rec.709%20V1_.cube",
        "DJI_Flip_D-LogM_to_Rec709.cube",
    ),
)


def get_dji_lut_catalog() -> list[DjiLutEntry]:
    return list(_DJI_LUT_CATALOG)


def get_dji_lut_catalog_by_category() -> dict[str, list[DjiLutEntry]]:
    grouped: dict[str, list[DjiLutEntry]] = {
        "pocket": [],
        "action": [],
        "drone": [],
    }
    for entry in _DJI_LUT_CATALOG:
        grouped.setdefault(entry.category, []).append(entry)
    return grouped


def destination_path(entry: DjiLutEntry) -> Path:
    return user_lut_dir() / entry.output_filename


def validate_downloaded_lut(path: str | Path) -> bool:
    cube = Path(path)
    if not cube.is_file():
        return False
    try:
        head = cube.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return False
    if "LUT_3D_SIZE" not in head.upper():
        return False
    return bool(re.search(r"^\s*[\d.eE+-]+\s+[\d.eE+-]+\s+[\d.eE+-]+\s*$", head, re.M))


def is_already_downloaded(entry: DjiLutEntry) -> bool:
    dest = destination_path(entry)
    return dest.is_file() and validate_downloaded_lut(dest)


def _http_download(url: str, dest: Path, opener: Callable | None = None) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PocketLiveCapture/1.0"},
    )
    open_fn = opener or urllib.request.urlopen
    with open_fn(request, timeout=120) as response, dest.open("wb") as handle:
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            handle.write(chunk)


def download_dji_lut(
    entry: DjiLutEntry,
    *,
    opener: Callable | None = None,
) -> Path:
    """下载单个 LUT；已存在且合法则跳过。"""
    dest = destination_path(entry)
    if dest.is_file():
        if validate_downloaded_lut(dest):
            return dest
        dest.unlink(missing_ok=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".cube.part")
    tmp_path = Path(tmp_name)
    try:
        import os

        os.close(tmp_fd)
        _http_download(entry.cdn_url, tmp_path, opener=opener)
        if not validate_downloaded_lut(tmp_path):
            raise RuntimeError("下载文件不是有效的 .cube LUT")
        tmp_path.replace(dest)
    except urllib.error.HTTPError as exc:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"CDN 返回 HTTP {exc.code}，链接可能已变更") from exc
    except urllib.error.URLError as exc:
        tmp_path.unlink(missing_ok=True)
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"网络不可用：{reason}") from exc
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"写入失败：{exc}") from exc
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return dest
