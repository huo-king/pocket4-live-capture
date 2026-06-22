# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — Pocket实况截图"""

from pathlib import Path

project_root = Path(SPECPATH).resolve()

datas = [
    (str(project_root / "app" / "styles" / "mimo_dark.qss"), "app/styles"),
    (str(project_root / "app" / "assets" / "watermark_osmo_pocket4.png"), "app/assets"),
    (str(project_root / "tools" / "ffmpeg.exe"), "tools"),
    (str(project_root / "tools" / "ffprobe.exe"), "tools"),
    (str(project_root / "tools" / "exiftool.exe"), "tools"),
    ('tools/exiftool_files', 'tools/exiftool_files'),
    (str(project_root / 'tools' / 'mi.config'), 'tools'),
    (str(project_root / "tools" / "realesrgan-ncnn-vulkan.exe"), "tools"),
    (str(project_root / "tools" / "vcomp140.dll"), "tools"),
    ('tools/models', 'tools/models'),
    ('app/assets/luts', 'app/assets/luts'),
]

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PIL.Image",
        "PIL.ImageQt",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Pocket实况截图",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Pocket实况截图",
)
