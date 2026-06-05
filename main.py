"""
Pocket Live Capture — Pocket实况截图工具
仿 DJI Mimo 交互，从 Pocket 4 原片导出安卓 Motion Photo

入口文件：创建 PySide6 应用窗口，加载深色主题，支持拖拽文件
"""

import sys
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent


# ── 项目根目录（用于加载资源） ──────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent


def load_stylesheet(path: str) -> str:
    """读取 QSS 样式文件内容"""
    full_path = Path(path)
    if not full_path.exists():
        # 尝试相对于本文件所在目录
        full_path = PROJECT_ROOT / path
    if full_path.exists():
        return full_path.read_text(encoding="utf-8")
    return ""


class MainWindow(QMainWindow):
    """主窗口 — 仿 Mimo 竖屏比例，深色主题，支持拖拽视频文件"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pocket实况截图")
        self.resize(900, 1600)  # 竖屏比例，模拟手机操作习惯
        self.setMinimumSize(480, 720)

        # 启用拖放
        self.setAcceptDrops(True)

        # 中心控件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 占位提示
        self.hint_label = QLabel("拖入视频文件开始")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #666666; font-size: 18px;")
        layout.addWidget(self.hint_label)

        self._last_dropped_path: str | None = None

    # ── 拖放事件 ──────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        """当文件拖入窗口时"""
        mime = event.mimeData()
        if mime.hasUrls():
            # 检查是否有支持的视频文件
            for url in mime.urls():
                path = url.toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in (".mp4", ".mov", ".m4v"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """文件释放时"""
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in (".mp4", ".mov", ".m4v"):
                    self._last_dropped_path = path
                    self.hint_label.setText(f"已加载:\n{path}")
                    self.hint_label.setStyleSheet("color: #4DA3FF; font-size: 14px;")
                    print(f"[INFO] 收到视频文件: {path}")
                    break
            else:
                self.hint_label.setText("不支持的格式\n请拖入 .mp4 / .mov 文件")
                self.hint_label.setStyleSheet("color: #FF6B6B; font-size: 14px;")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Pocket实况截图")
    app.setApplicationDisplayName("Pocket实况截图")

    # 加载深色主题样式
    qss = load_stylesheet("app/styles/mimo_dark.qss")
    if qss:
        app.setStyleSheet(qss)

    # 全局默认字体
    font = QFont("Microsoft YaHei UI", 10)
    font.setFamilies(["Microsoft YaHei UI", "Segoe UI", "微软雅黑", "sans-serif"])
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
