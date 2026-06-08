# Pocket实况截图

> 🎬 从 DJI Osmo Pocket 4 原视频导出安卓 Motion Photo（实况图），画质远超 DJI Mimo 压缩版。

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green?logo=qt)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey?logo=windows)
[![Download](https://img.shields.io/badge/下载-Windows%20exe-brightgreen?logo=windows)](https://github.com/huo-king/pocket-live-capture/releases)

---

## 📥 下载（开箱即用）

> **Windows 10/11 64 位用户**：下载解压后双击即可使用，无需安装 Python、FFmpeg 或任何运行环境。

👉 **[前往 GitHub Releases 下载最新版](https://github.com/huo-king/pocket-live-capture/releases)**

下载 `Pocket实况截图_vX.X_Windows_x64.zip`，解压后运行 `Pocket实况截图.exe`。

```
Pocket实况截图/
├── Pocket实况截图.exe    ← 双击启动
├── _internal/            ← 内置运行环境（勿删除）
└── 使用说明.txt
```

> ⚠️ 杀毒软件可能误报，可添加信任。分享给他人时打包整个文件夹为 zip。

---

## 📖 目录

- [📥 下载](#-下载开箱即用)
- [项目简介](#-项目简介)
- [功能亮点](#-功能亮点)
- [技术架构](#-技术架构)
- [从源码运行](#-从源码运行)
- [使用指南](#-使用指南)
- [画质策略](#-画质策略)
- [Motion Photo 格式说明](#-motion-photo-格式说明)
- [项目结构](#-项目结构)
- [开发指南](#-开发指南)
- [打包发布](#-打包发布)
- [常见问题](#-常见问题)
- [致谢](#-致谢)

---

## 🎯 项目简介

Pocket实况截图是一个 Windows 桌面工具，用于将 **DJI Osmo Pocket 4** 拍摄的原视频（MP4/MOV）导出为安卓手机支持的 **Motion Photo（实况图）**。

### 为什么需要这个工具？

| 对比项 | DJI Mimo App | Pocket实况截图 |
|--------|-------------|---------------|
| 视频质量 | 压缩重编码，画质下降 | **原画 stream copy，零重编码** |
| 封面质量 | 压缩 JPEG | **PNG 无损中转 → JPEG(q100/4:4:4)** |
| 水印 | 不可选 | 可开关，像素级叠加 |
| 批量处理 | 不支持 | 支持批量加水印 |
| 导出格式 | 仅实况图 | 实况图 / PNG 无损 / JPEG 最高质量 |

### 适用场景

- 从 Pocket 4 视频中提取高画质实况图，分享到安卓手机
- 导出单帧 PNG 无损截图（保留完整位深：10bit 源不截断为 8bit）
- 导出最高质量 JPEG 照片（quality=100，4:4:4 色度采样）
- 批量为已有照片 / 实况图添加 DJI Osmo Pocket 4 风格水印

---

## ✨ 功能亮点

### 核心功能

1. **Motion Photo 导出** — 生成 Google Motion Photo 1.0 + 小米相册兼容格式（`MVIMG_*.jpg`）
2. **PNG 无损照片** — 精确帧 → PNG(rgb48le) 全无损导出
3. **JPEG 最高质量照片** — PNG 无损中转 → JPEG(quality=100, 4:4:4)
4. **OSMO POCKET 4 水印** — 可开关，像素级叠加（logo 宽度 ≈ 画面 18%，位置与真机一致）
5. **批量水印** — 批量为已有 PNG/JPEG/实况图添加水印
6. **HEVC 预览代理** — Pocket 4 原片（HEVC）在 Windows 上需 H.264 代理预览，导出仍用原片

### 交互体验

- **拖拽加载** — 拖入视频文件即可开始
- **播放器控件** — 播放/暂停、时间轴拖拽定位
- **点击画面** — 单击画面切换播放/暂停
- **所见即所得** — 预览页确认封面效果再导出
- **DJI Mimo 风格深色主题** — 简洁专业的暗色 UI

---

## 🏗 技术架构

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **GUI 框架** | [PySide6](https://pypi.org/project/PySide6/) 6.11+ | Qt for Python，跨平台桌面 UI |
| **视频播放** | QMediaPlayer + QVideoWidget | Qt 多媒体框架 |
| **视频处理** | [FFmpeg](https://ffmpeg.org/) 7.x | 截帧、裁切、代理转码 |
| **视频探测** | [FFprobe](https://ffmpeg.org/ffprobe.html) | 读取视频元信息（编码、码率、时长等） |
| **元数据写入** | [ExifTool](https://exiftool.org/) 13.x | 写入 XMP/EXIF Motion Photo 元数据 |
| **图像处理** | [Pillow](https://pypi.org/project/Pillow/) 12.x | 图片格式转换、水印合成 |
| **打包发布** | [PyInstaller](https://pyinstaller.org/) 6.x | 单目录打包为独立 exe |

### 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     MainWindow                          │
│              (页面路由 + 导出编排)                         │
├──────────────┬──────────────────┬───────────────────────┤
│  PlayerPage  │ LivePreviewPage  │  BatchWatermarkPage   │
│  视频播放/截帧 │  实况预览/导出    │   批量水印处理          │
├──────────────┴──────────────────┴───────────────────────┤
│                  Service Layer                          │
├────────────┬────────────┬────────────┬─────────────────┤
│ FFmpegSvc  │ MotionPhoto│ PhotoPNG   │ PhotoJPEG        │
│ 视频裁切/截帧│ Svc 封装    │ Export     │ Export           │
├────────────┼────────────┼────────────┼─────────────────┤
│ PhotoWtrmk │ VideoProbe │ ProxyPrev  │ BatchWtrmk       │
│ 水印叠加    │ 视频探测    │ 预览代理    │ 批量水印          │
├────────────┴────────────┴────────────┴─────────────────┤
│                  External Tools                        │
├────────────┬────────────┬──────────────────────────────┤
│  FFmpeg    │  FFprobe   │  ExifTool                    │
└────────────┴────────────┴──────────────────────────────┘
```

### 数据流（Motion Photo 导出）

```
原视频 (HEVC/H.264)
    │
    ├──► ffprobe 探测视频信息
    │
    ├──► ffmpeg -ss 精确截帧 → PNG(rgb48le) 无损
    │       │
    │       ├── [可选] 叠水印 (FFmpeg overlay)
    │       │
    │       └──► Pillow → JPEG(q100/4:4:4) 封面
    │
    ├──► ffmpeg -c copy stream copy 视频片段 (3s)
    │       │
    │       └──► 原码率、零重编码
    │
    └──► 组装: JPEG封面 + MP4视频 + XMP元数据
            │
            └──► MVIMG_xxx.jpg (Google Motion Photo 1.0)
```

### 关键技术决策

#### 1. 封面画质：PNG 无损中转

不从视频直接编码为 JPEG，而是：
```
视频帧 → PNG(rgb48le) 无损解码 → Pillow JPEG(q100/4:4:4)
```

- `rgb48le` 像素格式保留完整位深（10bit 源不会压成 8bit）
- `compression_level=0` / `pred=mixed` 保证 PNG 阶段无压缩损失
- 最后 JPEG(q100/4:4:4) 是 JPEG 编码的最高质量参数

#### 2. 视频片段：Stream Copy 零重编码

```
ffmpeg -i input.mp4 -ss {start} -to {end} -c copy output.mp4
```

- `-c copy` 不经过解码→重编码过程，直接复制原始码流
- `-ss` 放在 `-i` 之后，确保帧精确裁切
- 实况视频质量 = 原片质量

#### 3. Motion Photo 封装：小米社区方案

```
JPEG 封面 (前置)
    + MP4 视频 (尾部附加)
    + XMP 元数据 (ExifTool 写入)
    ─────────────────────────────
    = MVIMG_*.jpg (安卓相册可识别)
```

- 先在 JPEG 尾部追加 MP4 视频字节
- 再用 ExifTool 写入 XMP-GCamera / XMP-GContainer 元数据
- 小米专用 EXIF 标签 `MVIMG`（通过 mi.config 自定义）

#### 4. HEVC 预览代理

Pocket 4 原片为 HEVC/H.265，但 Windows 原生不支持 HEVC 解码（需要付费扩展）。解决方案：

```
HEVC 原片 → ffmpeg 转码 → H.264 代理 (CRF 23, veryfast)
    │                            │
    │                            ├── 用于 Qt 播放预览
    │                            │
    └── 截帧/导出始终使用原片 ──────┘
```

- 代理缓存到临时目录，基于文件指纹复用
- 代理仅用于预览，导出保证原片画质

---

## 🚀 从源码运行

> 如果你不需要二次开发，直接下载 [预编译 exe](#-下载开箱即用) 即可，无需安装任何环境。

### 环境要求

- **OS:** Windows 10 / 11（理论上支持 macOS/Linux，未完整测试）
- **Python:** 3.10+
- **外部工具:** FFmpeg、ExifTool（见下方安装）

### 第一步：克隆项目

```powershell
git clone https://github.com/huo-king/pocket-live-capture.git
cd pocket-live-capture
```

### 第二步：安装外部工具

> ⚠️ 工具二进制文件（约 200MB）不在 Git 中，需要单独下载。

**方式一：自动安装（推荐）**

```powershell
powershell -ExecutionPolicy Bypass -File setup_tools.ps1
```

**方式二：手动安装**

将以下文件放入 `tools/` 目录：

| 文件 | 下载来源 |
|------|---------|
| `ffmpeg.exe` | https://ffmpeg.org/download.html （Windows gpl-shared build） |
| `ffprobe.exe` | 同上，与 ffmpeg 同包 |
| `exiftool.exe` | https://exiftool.org/ （Windows Executable） |
| `exiftool_files/` | 与 exiftool.exe 同目录 |

最终 `tools/` 目录结构：

```
tools/
├── ffmpeg.exe
├── ffprobe.exe
├── exiftool.exe
├── exiftool_files/   (ExifTool 的 Perl 库和配置文件)
└── mi.config         (小米 Motion Photo EXIF 配置，已在 Git 中)
```

### 第三步：安装 Python 依赖

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 第四步：运行

```powershell
python main.py
```

---

## 📘 使用指南

### 基础操作

1. **加载视频** — 拖入 `.mp4` / `.mov` 文件到窗口
2. **预览定位** — 播放视频，拖拽时间轴到目标画面
3. **选择导出类型：**

   | 按钮 | 功能 | 说明 |
   |------|------|------|
   | **PNG** | 导出 PNG 无损照片 | 当前帧，完整位深 |
   | **JPEG** | 导出 JPEG 最高质量照片 | PNG 无损中转为 JPEG(q100/4:4:4) |
   | **截实况** | 进入实况预览 | 预览封面效果，准备 Motion Photo 导出 |

4. **水印开关** — 勾选底部「添加水印」可叠加 DJI Osmo Pocket 4 logo

### 导出 Motion Photo（实况图）

1. 暂停到想要的画面 → 点击「**截实况**」
2. 进入预览页，确认封面效果
   - 无水印模式：视频播放预览（实时解码）
   - 有水印模式：PNG 原图预览（含水印效果）
3. 点击「**导出实况**」→ 选择保存位置
4. 生成的 `MVIMG_xxx.jpg`：
   - 包含 3 秒实况视频（暂停点 ± 1.5s）
   - 以暂停点为中心的封面帧

### 传到安卓手机

> ⚠️ **重要：** 请使用 USB 数据线复制到手机的 `DCIM/` 文件夹。**不要使用微信/QQ 传输**（它们会剥离实况数据，破坏 Motion Photo 结构）。

- **小米/HyperOS:** 系统相册直接支持实况播放
- **MIUI:** 若相册无动态效果，安装 Google 相册查看，或升级至 HyperOS
- **原生安卓 / Google 相册:** 直接支持

### 批量加水印

1. 点击底部「**批量水印**」
2. 添加 PNG / JPEG / MVIMG 文件（支持拖入）
3. 选择输出目录
4. 点击「开始批量加水印」

处理策略：
- **PNG** → 直接叠加水印（rgb48le）
- **JPEG** → PNG 无损解码 → 叠水印 → JPEG(q100/4:4:4)
- **实况图** → 仅重封装封面（视频字节原样复制，零重编码）

---

## 🎨 画质策略

### 全链路无损优先

```
                    ┌─ PNG 导出 ────────────────► 无损 rgb48le
                    │
视频帧 (10bit HEVC) ─┼─ JPEG 导出 ─── PNG 无损中转 ──► JPEG q100 4:4:4
                    │
                    ├─ 实况封面 ──── PNG 无损中转 ──► JPEG q100 4:4:4
                    │
                    └─ 实况视频 ──── stream copy ──► 原画质
```

### 各模式画质保证

| 模式 | 视频 | 封面 | 说明 |
|------|------|------|------|
| **实况** | Stream copy，零重编码 | PNG→JPEG(q100/4:4:4) | 视频与 Pocket 原片一致 |
| **PNG** | N/A | rgb48le 无损 | 保留完整位深 |
| **JPEG** | N/A | PNG 无损中转→JPEG(q100/4:4:4) | 最高 JPEG 参数 |
| **批量水印-实况** | 原样复制 | PNG 无损中转→JPEG(q100/4:4:4) | 视频字节不变 |

### 容错机制

- **非关键帧裁切失败检测** — 验证输出时长/体积/编码，不满足预期则报错提示
- **体积异常保护** — 输出小于原文件时中止，防止画质/数据受损
- **水印生效检测** — 输出与原文件完全相同时报错

---

## 📄 Motion Photo 格式说明

### 格式标准

项目生成的是 **Google Motion Photo 1.0** 格式（2024 年 Google 规范），同时兼容小米相册扩展。

### 文件结构

```
┌──────────────────────────────────────┐
│            MVIMG_xxx.jpg             │
├──────────────────────────────────────┤
│  JPEG 封面图像                        │
│  (高质量 4:4:4 JPEG)                  │
├──────────────────────────────────────┤
│  XMP 元数据                           │
│  ├─ GCamera:MotionPhoto = 1          │
│  ├─ GCamera:MotionPhotoVersion = 1   │
│  ├─ GCamera:MotionPhotoPresentation  │
│  │   TimestampUs = 1500000           │
│  ├─ GCamera:MicroVideo = 1           │
│  ├─ GCamera:MicroVideoVersion = 1    │
│  ├─ GCamera:MicroVideoOffset = N     │
│  ├─ GCamera:MicroVideoPresentation   │
│  │   TimestampUs = 1500000           │
│  └─ GContainer:ContainerDirectory    │
│       = [{Item={Mime=image/jpeg}},    │
│          {Item={Mime=video/mp4}}]    │
├──────────────────────────────────────┤
│  EXIF 小米标签                        │
│  └─ MVIMG = 1 (0x8897)              │
├──────────────────────────────────────┤
│  MP4 视频数据 (原画 stream copy)       │
│  ┌────────────────────────────────┐  │
│  │ ftyp + moov + mdat atoms       │  │
│  │ (约 3 秒，暂停点 ± 1.5s)        │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

### 文件名规范

- 必须以 `MVIMG_` 开头（安卓相册识别规则）
- 格式: `MVIMG_{原视频名}_{mm}m{ss}s{mmm}.jpg`
- 示例: `MVIMG_DJI_2024_001_01m23s456.jpg`

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| MotionPhotoPresentationTimestampUs | 1,500,000 | 封面帧在视频中的偏移（微秒） |
| MicroVideoOffset | 视频字节数 | 视频数据在文件中的字节偏移 |
| 视频片段长度 | 3 秒 | 封面帧 ± 1.5 秒 |

---

## 📁 项目结构

```
pocket-live-capture/
├── main.py                          # 程序入口
├── requirements.txt                 # Python 依赖
├── build.spec                       # PyInstaller 打包配置
├── setup_tools.ps1                  # 外部工具下载脚本
├── .gitignore
├── README.md
│
├── app/
│   ├── main_window.py               # 主窗口 — 页面路由与导出编排
│   │
│   ├── models/
│   │   └── capture_task.py          # 截图任务数据模型
│   │
│   ├── pages/
│   │   ├── player_page.py           # 页面1：视频播放 + 截帧
│   │   ├── live_preview_page.py     # 页面2：实况预览 + 导出
│   │   ├── batch_watermark_page.py  # 页面3：批量加水印
│   │   └── capture_type_page.py     # 导出类型选择弹层
│   │
│   ├── widgets/
│   │   ├── video_player.py          # QMediaPlayer 封装
│   │   ├── bottom_toolbar.py        # 底部工具栏
│   │   ├── player_bottom_panel.py   # 播放器底部面板
│   │   ├── timeline_slider.py       # 时间轴滑块
│   │   ├── processing_panel.py      # 处理状态面板
│   │   ├── watermark_preview_panel.py # 水印预览面板
│   │   └── export_progress.py       # 导出进度对话框
│   │
│   ├── services/
│   │   ├── export_worker.py         # 后台导出线程 (QThread)
│   │   ├── ffmpeg_service.py        # FFmpeg 视频裁切/截帧
│   │   ├── motion_photo_service.py  # Motion Photo 封装
│   │   ├── photo_png_export.py      # PNG 无损导出
│   │   ├── photo_jpeg_export.py     # JPEG 最高质量导出
│   │   ├── photo_watermark.py       # 水印叠加（像素级）
│   │   ├── video_probe.py           # FFprobe 视频信息读取
│   │   ├── tool_paths.py            # 外部工具路径解析
│   │   ├── subprocess_util.py       # 子进程执行工具
│   │   ├── proxy_preview_service.py # HEVC 预览代理服务
│   │   ├── proxy_preview_worker.py  # 预览代理后台线程
│   │   ├── preview_worker.py        # 预览帧生成线程
│   │   ├── batch_watermark_service.py # 批量水印处理
│   │   └── batch_watermark_worker.py  # 批量水印后台线程
│   │
│   ├── styles/
│   │   └── mimo_dark.qss            # DJI Mimo 风格深色主题
│   │
│   └── assets/
│       └── watermark_osmo_pocket4.png # 水印素材
│
└── tools/
    ├── mi.config                     # 小米 EXIF 配置
    ├── ffmpeg.exe                    # (需下载)
    ├── ffprobe.exe                   # (需下载)
    ├── exiftool.exe                  # (需下载)
    └── exiftool_files/              # (需下载)
```

---

## 🔧 开发指南

### 开发环境搭建

```powershell
# 克隆项目
git clone https://github.com/huo-king/pocket-live-capture.git
cd pocket-live-capture

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 下载外部工具
powershell -ExecutionPolicy Bypass -File setup_tools.ps1

# 启动开发模式
python main.py
```

### 依赖说明

```text
PySide6==6.11.1    # Qt for Python GUI 框架
Pillow==12.2.0     # Python 图像处理库
```

> 项目刻意保持依赖精简。所有视频处理通过 FFmpeg 命令行完成，元数据通过 ExifTool 写入，不引入额外的 Python 包装库。

### 代码规范

- **类型标注** — 所有函数都有类型标注（`from __future__ import annotations`）
- **文档字符串** — 模块/类/方法都有清晰的 docstring
- **单文件职责** — 每个模块只负责一个独立功能
- **信号槽解耦** — 页面间通过 Qt Signal 通信，不直接依赖

### 添加新功能

1. **新增导出格式** — 在 `app/services/` 添加模块，仿照 `photo_png_export.py`
2. **新增水印样式** — 替换 `app/assets/watermark_osmo_pocket4.png`
3. **新增页面** — 在 `app/pages/` 添加，注册到 `MainWindow.stack`
4. **修改 UI** — 编辑 `app/styles/mimo_dark.qss`

---

## 📦 打包发布

```powershell
pip install pyinstaller
pyinstaller build.spec
```

输出在 `dist/Pocket实况截图/`，包含：
- `Pocket实况截图.exe` — 主程序
- `_internal/` — Python 运行时和依赖
- `_internal/tools/` — 内置的 FFmpeg / ExifTool
- `_internal/app/` — Qt 样式和素材

### 分发给用户

将整个 `dist/Pocket实况截图/` 文件夹打包为 ZIP，用户解压后双击 `Pocket实况截图.exe` 即可使用。

---

## ❓ 常见问题

<details>
<summary><b>Q: 为什么 Windows 上播放不了 Pocket 4 的视频？</b></summary>

Pocket 4 拍摄的是 HEVC/H.265 编码。Windows 默认不支持 HEVC 解码（需从 Microsoft Store 购买「HEVC 视频扩展」）。

本工具会自动生成 H.264 预览代理，不影响导出画质。
</details>

<details>
<summary><b>Q: 导出实况时提示「无法无损裁切此位置的视频片段」？</b></summary>

-stream copy 裁切要求起点落在 I 帧（关键帧）上。**微调时间轴**（前后拖动几帧）再导出即可。工具会严格验证输出时长和码率，不通过则拒绝导出。
</details>

<details>
<summary><b>Q: 传到手机后，相册看不到实况效果？</b></summary>

1. **传输方式** — 必须用 USB 复制到 `DCIM/` 文件夹，微信/QQ 会剥离 Motion Photo 数据
2. **文件名** — 确保以 `MVIMG_` 开头
3. **MIUI 用户** — 老版本 MIUI 不完全支持，可安装 Google 相册查看，或升级到 HyperOS
</details>

<details>
<summary><b>Q: 实况图和普通照片有什么区别？</b></summary>

实况图是包含短视频片段的 JPEG 文件。在安卓相册中长按图片，会播放约 3 秒的实况视频（类似 iPhone Live Photo）。
</details>

<details>
<summary><b>Q: 为什么 JPEG 不直接从视频截取，要先转 PNG？</b></summary>

FFmpeg 内置的 JPEG 编码器不支持 quality=100 + 4:4:4 色度采样的组合。通过 PNG 无损中转，再用 Pillow（libjpeg-turbo）编码，可以达到 JPEG 的最高质量。
</details>

---

## 🙏 致谢

- [FFmpeg](https://ffmpeg.org/) — 视频处理核心引擎
- [ExifTool](https://exiftool.org/) — 元数据写入
- [Serendo/LivePhoto2XiaomiPhoto](https://github.com/Serendo/LivePhoto2XiaomiPhoto) — 小米 Motion Photo 格式参考
- [Google Motion Photo Spec](https://developer.android.com/media/platform/motion-photo-format) — Google Motion Photo 格式规范
- DJI Mimo App — UI 交互参考

---

## 📝 License

MIT License — 详见 [LICENSE](LICENSE) 文件。
