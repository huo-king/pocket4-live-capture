"""查找 FFmpeg / ExifTool 可执行文件路径"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal = exe_dir / "_internal"
        if internal.is_dir():
            return internal
        return exe_dir
    return PROJECT_ROOT


def resolve_tool(name: str) -> str:
    """
    按优先级查找外部工具：
    1. tools/{name}.exe（打包内置）
    2. 系统 PATH
    """
    exe = f"{name}.exe" if os.name == "nt" else name
    bundled = _bundle_root() / "tools" / exe
    if bundled.is_file():
        return str(bundled)

    found = shutil.which(name)
    if found:
        return found

    raise FileNotFoundError(
        f"未找到 {name}。请安装 {name} 并加入 PATH，"
        f"或将 {exe} 放到 { _bundle_root() / 'tools' }"
    )
