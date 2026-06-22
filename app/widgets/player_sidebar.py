"""播放页左侧功能磁贴栏 — 翻转展开各功能选项。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.lut_presets import BUILTIN_LUT_PRESETS
from app.services.lut_service import (
    LUT_DISABLED,
    LutConfig,
    default_builtin_lut_path,
    import_lut_file,
    list_available_luts,
    preset_label_for_path,
)
from app.services.quality_enhance_service import (
    DEFAULT_ENHANCE_TIER,
    ENHANCE_TIER_OPTIONS,
    EnhanceMode,
    get_tier_option,
    should_enhance_motion_video,
)
from app.widgets.flip_tile import FlipTile
from app.widgets.sidebar_header import SidebarHeader

GITHUB_URL = "https://github.com/huo-king/pocket-live-capture/releases"


class PlayerSidebar(QWidget):
    png_photo_clicked = Signal()
    jpeg_photo_clicked = Signal()
    live_clicked = Signal()
    batch_watermark_clicked = Signal()
    watermark_changed = Signal(bool)
    quality_enhance_changed = Signal(bool)
    quality_enhance_mode_changed = Signal(object)
    lut_changed = Signal(bool)
    lut_config_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("playerSidebar")
        self.setFixedWidth(204)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._lut_path = default_builtin_lut_path()
        self._lut_strength = 100
        self._stack_lut_path = ""
        self._stack_strength = 80
        self._stack_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 6, 8)
        layout.setSpacing(6)

        layout.addWidget(SidebarHeader())

        self.enhance_tile = FlipTile(
            "画质\n增强",
            "原画直出",
            accent="#FFB347",
            icon="✦",
        )
        self.capture_tile = FlipTile(
            "截取",
            "PNG · JPEG · 实况",
            accent="#4DA3FF",
            icon="◉",
        )
        self.lut_tile = FlipTile("LUT", "色彩还原", accent="#E879A6", icon="◈")
        self.batch_tile = FlipTile("批量", "水印 / 更多", accent="#9B8CFF", icon="▤")

        self._tiles = (
            self.enhance_tile,
            self.capture_tile,
            self.lut_tile,
            self.batch_tile,
        )
        self._expanded_tile: FlipTile | None = None

        for tile in self._tiles:
            layout.addWidget(tile, stretch=1)
            tile.flipped_changed.connect(
                lambda flipped, t=tile: self._on_tile_flipped(t, flipped)
            )

        layout.addStretch(0)

        self.enhance_tile.set_back_widget(self._build_enhance_back())
        self.capture_tile.set_back_widget(self._build_capture_back())
        self.lut_tile.set_back_widget(self._build_lut_back())
        self.batch_tile.set_back_widget(self._build_batch_back())

        self._emit_lut_config()

    def _build_enhance_back(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.enhance_cb = QCheckBox("开启画质增强")
        self.enhance_cb.setChecked(False)
        self.enhance_cb.toggled.connect(self._on_enhance_toggled)
        layout.addWidget(self.enhance_cb)

        hint = QLabel("勾选后选档位；可与截实况/Png/Jpeg 同时使用")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(hint)

        self._tier_group = QButtonGroup(panel)
        self._tier_radios: list[QRadioButton] = []
        self._tier_panel = QWidget()
        tier_layout = QVBoxLayout(self._tier_panel)
        tier_layout.setContentsMargins(0, 0, 0, 0)
        tier_layout.setSpacing(2)
        self._tier_panel.setVisible(False)

        default_index = next(
            (
                i
                for i, tier in enumerate(ENHANCE_TIER_OPTIONS)
                if tier.mode == DEFAULT_ENHANCE_TIER
            ),
            1,
        )
        for i, tier in enumerate(ENHANCE_TIER_OPTIONS):
            radio = QRadioButton(tier.label)
            radio.setObjectName("enhanceTierRadio")
            radio.setToolTip(f"{tier.subtitle}\n{tier.description}")
            radio.setStyleSheet("font-size: 11px;")
            self._tier_group.addButton(radio, i)
            tier_layout.addWidget(radio)
            self._tier_radios.append(radio)
        self._tier_radios[default_index].setChecked(True)
        self._tier_group.idClicked.connect(self._on_tier_selected)
        layout.addWidget(self._tier_panel)
        layout.addStretch()
        return panel

    def _build_capture_back(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.watermark_cb = QCheckBox("水印")
        self.watermark_cb.toggled.connect(self.watermark_changed.emit)
        layout.addWidget(self.watermark_cb)

        self.capture_hint_label = QLabel("")
        self.capture_hint_label.setWordWrap(True)
        self.capture_hint_label.setStyleSheet("color: #4DA3FF; font-size: 10px;")
        layout.addWidget(self.capture_hint_label)

        self.png_btn = self._small_btn("PNG", self._on_png_clicked)
        self.jpeg_btn = self._small_btn("JPEG", self._on_jpeg_clicked)
        self.live_btn = self._small_btn("截实况", self._on_live_clicked, accent=True)
        layout.addWidget(self.png_btn)
        layout.addWidget(self.jpeg_btn)
        layout.addWidget(self.live_btn)
        layout.addStretch()
        return panel

    def _build_lut_back(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.lut_cb = QCheckBox("启用 LUT")
        self.lut_cb.toggled.connect(self._on_lut_toggled)
        layout.addWidget(self.lut_cb)

        self.lut_combo = QComboBox()
        self.lut_combo.setObjectName("lutPresetCombo")
        self.lut_combo.setVisible(False)
        self.lut_combo.currentIndexChanged.connect(self._on_lut_preset_changed)
        layout.addWidget(self.lut_combo)

        import_row = QHBoxLayout()
        import_row.setSpacing(4)
        self.lut_pick_btn = QPushButton("导入")
        self.lut_pick_btn.setToolTip("导入本地 .cube 文件")
        self.lut_pick_btn.setVisible(False)
        self.lut_pick_btn.clicked.connect(self._pick_lut_file)
        self.dji_download_btn = QPushButton("官方 LUT")
        self.dji_download_btn.setObjectName("djiLutSidebarBtn")
        self.dji_download_btn.setToolTip("从 DJI CDN 下载官方色彩还原 LUT")
        self.dji_download_btn.setVisible(False)
        self.dji_download_btn.clicked.connect(self._open_dji_lut_dialog)
        import_row.addWidget(self.lut_pick_btn, stretch=1)
        import_row.addWidget(self.dji_download_btn, stretch=1)
        layout.addLayout(import_row)

        self.lut_name_label = QLabel("")
        self.lut_name_label.setWordWrap(True)
        self.lut_name_label.setVisible(False)
        self.lut_name_label.setMaximumHeight(32)
        self.lut_name_label.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(self.lut_name_label)

        strength_row = QHBoxLayout()
        strength_row.setSpacing(4)
        self.lut_slider = QSlider(Qt.Orientation.Horizontal)
        self.lut_slider.setRange(0, 100)
        self.lut_slider.setValue(100)
        self.lut_slider.setVisible(False)
        self.lut_slider.valueChanged.connect(self._on_lut_strength_changed)
        self.lut_strength_label = QLabel("100%")
        self.lut_strength_label.setVisible(False)
        self.lut_strength_label.setFixedWidth(32)
        self.lut_strength_label.setStyleSheet("color: #AAAAAA; font-size: 10px;")
        strength_row.addWidget(self.lut_slider, stretch=1)
        strength_row.addWidget(self.lut_strength_label)
        layout.addLayout(strength_row)

        self.lut_stack_cb = QCheckBox("叠加 LUT")
        self.lut_stack_cb.setToolTip("在主 LUT 之上再叠一个 LUT，可组合出更丰富的色调")
        self.lut_stack_cb.setVisible(False)
        self.lut_stack_cb.toggled.connect(self._on_lut_stack_toggled)
        layout.addWidget(self.lut_stack_cb)

        self.lut_stack_combo = QComboBox()
        self.lut_stack_combo.setObjectName("lutStackCombo")
        self.lut_stack_combo.setVisible(False)
        self.lut_stack_combo.currentIndexChanged.connect(self._on_lut_stack_preset_changed)
        layout.addWidget(self.lut_stack_combo)

        stack_strength_row = QHBoxLayout()
        stack_strength_row.setSpacing(4)
        self.lut_stack_slider = QSlider(Qt.Orientation.Horizontal)
        self.lut_stack_slider.setRange(0, 100)
        self.lut_stack_slider.setValue(80)
        self.lut_stack_slider.setVisible(False)
        self.lut_stack_slider.valueChanged.connect(self._on_lut_stack_strength_changed)
        self.lut_stack_strength_label = QLabel("80%")
        self.lut_stack_strength_label.setVisible(False)
        self.lut_stack_strength_label.setFixedWidth(32)
        self.lut_stack_strength_label.setStyleSheet("color: #AAAAAA; font-size: 10px;")
        stack_strength_row.addWidget(self.lut_stack_slider, stretch=1)
        stack_strength_row.addWidget(self.lut_stack_strength_label)
        layout.addLayout(stack_strength_row)

        self.lut_preview_cb = QCheckBox("对比预览")
        self.lut_preview_cb.setToolTip(
            "右侧并排显示 LUT 效果，与左侧原片同步对比（导出仍无损）"
        )
        self.lut_preview_cb.setChecked(True)
        self.lut_preview_cb.setVisible(False)
        self.lut_preview_cb.toggled.connect(self._emit_lut_config)
        layout.addWidget(self.lut_preview_cb)
        layout.addStretch()
        return panel

    def _on_tile_flipped(self, tile: FlipTile, flipped: bool) -> None:
        """展开磁贴时隐藏其余磁贴，让当前面板占满侧边栏高度。"""
        layout = self.layout()
        if flipped:
            for other in self._tiles:
                if other is not tile and other.is_flipped():
                    other.set_flipped(False, animate=False)
            self._expanded_tile = tile
            for other in self._tiles:
                other.setVisible(other is tile)
            idx = layout.indexOf(tile)
            if idx >= 0:
                layout.setStretch(idx, 1)
            return

        if self._expanded_tile is tile:
            self._expanded_tile = None
        for other in self._tiles:
            other.setVisible(True)
            idx = layout.indexOf(other)
            if idx >= 0:
                layout.setStretch(idx, 1)

    def _build_batch_back(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.batch_btn = self._small_btn(
            "批量水印", self.batch_watermark_clicked.emit
        )
        layout.addWidget(self.batch_btn)

        github = QLabel('<a href="#" style="color:#888;">GitHub</a>')
        github.setOpenExternalLinks(False)
        github.linkActivated.connect(lambda _u: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        github.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(github)
        layout.addStretch()
        return panel

    @staticmethod
    def _small_btn(text: str, slot, *, accent: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(32)
        if accent:
            btn.setObjectName("accentButton")
        btn.clicked.connect(slot)
        return btn

    def _on_png_clicked(self) -> None:
        self.png_photo_clicked.emit()

    def _on_jpeg_clicked(self) -> None:
        self.jpeg_photo_clicked.emit()

    def _on_live_clicked(self) -> None:
        self.live_clicked.emit()

    def _on_tier_selected(self, _index: int) -> None:
        self._emit_enhance_mode()
        self._refresh_enhance_tile_front()
        self._refresh_capture_hint()

    def _on_enhance_toggled(self, checked: bool) -> None:
        self._tier_panel.setVisible(checked)
        for radio in self._tier_radios:
            radio.setEnabled(checked)
        self.quality_enhance_changed.emit(checked)
        self._emit_enhance_mode()
        self._refresh_enhance_tile_front()
        self._refresh_capture_hint()

    def _emit_enhance_mode(self) -> None:
        self.quality_enhance_mode_changed.emit(self.get_enhance_mode())

    def _refresh_enhance_tile_front(self) -> None:
        if not self.enhance_cb.isChecked():
            self.enhance_tile.title_label.setText("画质\n增强")
            self.enhance_tile.set_subtitle("原画直出")
            return
        tier = get_tier_option(self.get_enhance_mode())
        label = tier.label if tier else "已开启"
        self.enhance_tile.title_label.setText("画质\n增强")
        self.enhance_tile.set_subtitle(f"已开 · {label}")

    def _refresh_capture_hint(self) -> None:
        if not self.enhance_cb.isChecked():
            self.capture_hint_label.setText("")
            return
        mode = self.get_enhance_mode()
        tier = get_tier_option(mode)
        if tier is None:
            self.capture_hint_label.setText("画质增强已开，可直接截实况")
            return
        if should_enhance_motion_video(mode):
            self.capture_hint_label.setText(
                f"已选「{tier.label}」· 封面+内嵌视频均增强，可直接点截实况"
            )
        else:
            self.capture_hint_label.setText(
                f"已选「{tier.label}」· 封面增强+视频原画，可直接点截实况"
            )

    def _open_dji_lut_dialog(self) -> None:
        from app.widgets.dji_lut_dialog import DjiLutDownloadDialog

        dialog = DjiLutDownloadDialog(self)
        dialog.lut_downloaded.connect(self._on_dji_luts_downloaded)
        dialog.exec()

    def _on_dji_luts_downloaded(self, paths: list[str]) -> None:
        if not paths:
            return
        self._reload_lut_combo()
        if self._stack_enabled:
            self._reload_lut_stack_combo()
        if paths:
            self._select_lut_path(paths[-1])
            self._emit_lut_config()

    def _on_lut_toggled(self, checked: bool) -> None:
        self.lut_combo.setVisible(checked)
        self.lut_pick_btn.setVisible(checked)
        self.dji_download_btn.setVisible(checked)
        self.lut_name_label.setVisible(checked)
        self.lut_slider.setVisible(checked)
        self.lut_strength_label.setVisible(checked)
        self.lut_stack_cb.setVisible(checked)
        self._sync_lut_stack_visible()
        self.lut_preview_cb.setVisible(checked)
        self._sync_lut_preview_cb_enabled()
        self._sync_lut_stack_enabled()
        if checked:
            self._reload_lut_combo()
            if not Path(self._lut_path).is_file():
                self._lut_path = default_builtin_lut_path()
            self._select_lut_path(self._lut_path)
            if self._stack_enabled and not self._stack_lut_path:
                self._stack_lut_path = self._default_stack_lut_path()
            self._reload_lut_stack_combo()
        self.lut_changed.emit(checked)
        self._emit_lut_config()

    def _default_stack_lut_path(self) -> str:
        for path in list_available_luts():
            if str(path) != self._lut_path:
                return str(path)
        return ""

    def _on_lut_stack_toggled(self, checked: bool) -> None:
        self._stack_enabled = checked
        if checked and not self._stack_lut_path:
            self._stack_lut_path = self._default_stack_lut_path()
            self._reload_lut_stack_combo()
        self._sync_lut_stack_visible()
        self._sync_lut_stack_enabled()
        self._emit_lut_config()

    def _sync_lut_stack_visible(self) -> None:
        show = self.lut_cb.isChecked() and self._stack_enabled
        self.lut_stack_combo.setVisible(show)
        self.lut_stack_slider.setVisible(show)
        self.lut_stack_strength_label.setVisible(show)

    def _sync_lut_stack_enabled(self) -> None:
        lut_on = self.lut_cb.isEnabled() and self.lut_cb.isChecked()
        stack_on = lut_on and self._stack_enabled
        self.lut_stack_cb.setEnabled(lut_on)
        self.lut_stack_combo.setEnabled(stack_on)
        self.lut_stack_slider.setEnabled(stack_on)

    def _reload_lut_stack_combo(self) -> None:
        current = self._stack_lut_path
        self.lut_stack_combo.blockSignals(True)
        self.lut_stack_combo.clear()
        for path in list_available_luts():
            if str(path) == self._lut_path:
                continue
            self.lut_stack_combo.addItem(preset_label_for_path(path), str(path))
        self.lut_stack_combo.blockSignals(False)
        if current and current != self._lut_path:
            self._select_stack_lut_path(current)
        elif self.lut_stack_combo.count() > 0:
            self.lut_stack_combo.setCurrentIndex(0)
            data = self.lut_stack_combo.currentData()
            if data:
                self._stack_lut_path = str(data)

    def _select_stack_lut_path(self, path: str) -> None:
        for i in range(self.lut_stack_combo.count()):
            if self.lut_stack_combo.itemData(i) == path:
                self.lut_stack_combo.setCurrentIndex(i)
                self._stack_lut_path = path
                return

    def _on_lut_stack_preset_changed(self, _index: int) -> None:
        data = self.lut_stack_combo.currentData()
        if data:
            self._stack_lut_path = str(data)
            self._emit_lut_config()

    def _on_lut_stack_strength_changed(self, value: int) -> None:
        self._stack_strength = value
        self.lut_stack_strength_label.setText(f"{value}%")
        self._emit_lut_config()

    def _reload_lut_combo(self) -> None:
        current = self._lut_path
        self.lut_combo.blockSignals(True)
        self.lut_combo.clear()
        for path in list_available_luts():
            label = preset_label_for_path(path)
            self.lut_combo.addItem(label, str(path))
        self.lut_combo.blockSignals(False)
        if current:
            self._select_lut_path(current)
        if self._stack_enabled:
            self._reload_lut_stack_combo()

    def _select_lut_path(self, path: str) -> None:
        for i in range(self.lut_combo.count()):
            if self.lut_combo.itemData(i) == path:
                self.lut_combo.setCurrentIndex(i)
                self._lut_path = path
                self._update_lut_name_label()
                return
        if self.lut_combo.count() > 0:
            self.lut_combo.setCurrentIndex(0)
            data = self.lut_combo.currentData()
            if data:
                self._lut_path = str(data)
                self._update_lut_name_label()

    def _on_lut_preset_changed(self, _index: int) -> None:
        data = self.lut_combo.currentData()
        if data:
            self._lut_path = str(data)
            self._update_lut_name_label()
            if self._stack_lut_path == self._lut_path:
                self._stack_lut_path = self._default_stack_lut_path()
                self._reload_lut_stack_combo()
            self._emit_lut_config()

    def _update_lut_name_label(self) -> None:
        name = Path(self._lut_path).name
        for preset in BUILTIN_LUT_PRESETS:
            if preset.filename == name:
                self.lut_name_label.setText(preset.description)
                self.lut_name_label.setStyleSheet("color: #888888; font-size: 10px;")
                return
        self.lut_name_label.setText("自定义 LUT · 可免费导入更多 .cube")
        self.lut_name_label.setStyleSheet("color: #888888; font-size: 10px;")

    def _on_lut_strength_changed(self, value: int) -> None:
        self._lut_strength = value
        self.lut_strength_label.setText(f"{value}%")
        self._emit_lut_config()

    def _pick_lut_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 LUT 文件",
            str(Path.home()),
            "Cube LUT (*.cube)",
        )
        if not path:
            return
        try:
            dest = import_lut_file(path)
        except ValueError as exc:
            self.lut_name_label.setText(str(exc))
            self.lut_name_label.setStyleSheet("color: #FF8866; font-size: 10px;")
            return
        self._lut_path = str(dest)
        self._reload_lut_combo()
        self._select_lut_path(self._lut_path)
        self._emit_lut_config()

    def _emit_lut_config(self) -> None:
        config = self.get_lut_config()
        self.lut_config_changed.emit(config)

    def get_lut_config(self) -> LutConfig:
        if not self.lut_cb.isChecked():
            return LUT_DISABLED
        return LutConfig(
            enabled=True,
            lut_path=self._lut_path,
            strength=self._lut_strength,
            stack_lut_path=self._stack_lut_path if self._stack_enabled else "",
            stack_strength=self._stack_strength,
        )

    def is_lut_preview_enabled(self) -> bool:
        return (
            self.lut_cb.isChecked()
            and self.lut_preview_cb.isChecked()
            and self.get_lut_config().active
        )

    def is_watermark_enabled(self) -> bool:
        return self.watermark_cb.isChecked()

    def get_enhance_mode(self) -> EnhanceMode:
        if not self.enhance_cb.isChecked():
            return EnhanceMode.OFF
        index = self._tier_group.checkedId()
        if 0 <= index < len(ENHANCE_TIER_OPTIONS):
            return ENHANCE_TIER_OPTIONS[index].mode
        return DEFAULT_ENHANCE_TIER

    def _sync_lut_preview_cb_enabled(self) -> None:
        self.lut_preview_cb.setEnabled(
            self.lut_cb.isEnabled() and self.lut_cb.isChecked()
        )

    def set_enabled(self, enabled: bool) -> None:
        self.enhance_cb.setEnabled(enabled)
        checked = self.enhance_cb.isChecked()
        for radio in self._tier_radios:
            radio.setEnabled(enabled and checked)
        self.watermark_cb.setEnabled(enabled)
        self.lut_cb.setEnabled(enabled)
        self.lut_combo.setEnabled(enabled)
        self.lut_pick_btn.setEnabled(enabled)
        self.dji_download_btn.setEnabled(enabled)
        self.lut_slider.setEnabled(enabled)
        self._sync_lut_stack_enabled()
        self._sync_lut_preview_cb_enabled()
        self.png_btn.setEnabled(enabled)
        self.jpeg_btn.setEnabled(enabled)
        self.live_btn.setEnabled(enabled)
        self.batch_btn.setEnabled(True)

        for tile in (
            self.enhance_tile,
            self.capture_tile,
            self.lut_tile,
            self.batch_tile,
        ):
            tile.setEnabled(enabled)

        if enabled and self._expanded_tile is not None:
            self._on_tile_flipped(self._expanded_tile, True)

        if enabled:
            if not Path(self._lut_path).is_file():
                self._lut_path = default_builtin_lut_path()
            self._reload_lut_combo()

        self._refresh_enhance_tile_front()
        self._refresh_capture_hint()
