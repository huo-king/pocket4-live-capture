"""
Pocket Live Capture — Pocket实况截图工具
仿 DJI Mimo 交互，从 Pocket 4 原片导出安卓 Motion Photo
"""

import os
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parent


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        from app.services.tool_paths import _bundle_root

        return _bundle_root()
    return PROJECT_ROOT


def setup_tool_path() -> None:
    """将 tools/ 加入 PATH，供 ExifTool 调用"""
    tools_dir = _app_root() / "tools"
    if tools_dir.is_dir():
        current = os.environ.get("PATH", "")
        if str(tools_dir) not in current.split(os.pathsep):
            os.environ["PATH"] = str(tools_dir) + os.pathsep + current


def load_stylesheet(path: str) -> str:
    full_path = _app_root() / path
    if full_path.exists():
        return full_path.read_text(encoding="utf-8")
    return ""


def main():
    setup_tool_path()

    from app.services.lut_service import ensure_builtin_luts

    ensure_builtin_luts()

    from PySide6.QtCore import Qt

    from app.main_window import MainWindow

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Pocket实况截图")
    app.setApplicationDisplayName("Pocket实况截图")

    qss = load_stylesheet("app/styles/mimo_dark.qss")
    if qss:
        app.setStyleSheet(qss)

    font = QFont("Microsoft YaHei UI", 10)
    font.setFamilies(["Microsoft YaHei UI", "Segoe UI", "微软雅黑", "sans-serif"])
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
