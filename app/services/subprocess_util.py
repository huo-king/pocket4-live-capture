"""subprocess 文本捕获 — 避免 Windows 默认 GBK 解码 FFmpeg 输出时崩溃"""

from __future__ import annotations

import subprocess
from typing import Any


def run_text(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    check = kwargs.pop("check", False)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
        **kwargs,
    )
