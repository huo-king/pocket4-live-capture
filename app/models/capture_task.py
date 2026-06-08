"""一次截图任务的数据模型"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CaptureTask:
    video_path: str
    timestamp_ms: int
    total_duration_sec: float = 0.0
    clip_start_sec: float = 0.0
    clip_duration_sec: float = 3.0
    presentation_us: int = 1_500_000

    @property
    def timestamp_sec(self) -> float:
        return self.timestamp_ms / 1000.0

    def compute_clip_bounds(self, total_duration_sec: float) -> None:
        """以暂停时刻为中心计算 3 秒片段边界（片头片尾自动截断）"""
        self.total_duration_sec = max(0.0, total_duration_sec)
        center = self.timestamp_sec
        start = max(0.0, center - 1.5)
        end = min(self.total_duration_sec, center + 1.5)
        self.clip_start_sec = start
        self.clip_duration_sec = max(0.0, end - start)
        offset = center - start
        self.presentation_us = int(offset * 1_000_000)
